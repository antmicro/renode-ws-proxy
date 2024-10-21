// Copyright (c) 2024 Antmicro <www.antmicro.com>
//
// SPDX-License-Identifier: Apache-2.0

import { z } from 'zod';
import * as s from './schema';
import WebSocket from 'isomorphic-ws';
import { Buffer } from 'buffer';
import { tryConnectWs, tryJsonParse } from './utils';
import {
  GetSensorValue,
  Sensor,
  SensorType,
  SensorTypeFromString,
  SensorValue,
} from './sensor';

class SocketClosedEvent extends Event {
  constructor() {
    super('close');
  }
}

export class RenodeProxySession extends EventTarget {
  private requestQueue: RequestCallback[] = [];

  public static async tryConnect(wsUri: string, workspace: string) {
    const uri = new URL(`/proxy/${workspace}`, wsUri);
    const socket = await tryConnectWs(uri.toString());
    return new RenodeProxySession(socket, wsUri);
  }

  private constructor(
    private sessionSocket: WebSocket,
    private sessionUri: string,
  ) {
    super();
    this.sessionSocket.addEventListener('message', ev =>
      this.onData(ev.data.toString()),
    );
    this.sessionSocket.addEventListener('error', () => this.onError());
    this.sessionSocket.addEventListener('close', () => this.onClose());
  }

  public get sessionBase(): string {
    return this.sessionUri;
  }

  public get socketReady() {
    let state = this.sessionSocket.readyState ?? WebSocket.CLOSED;
    return state === WebSocket.OPEN;
  }

  public startRenode(cwd?: string): Promise<any> {
    return this.sendSessionRequest({
      action: 'spawn',
      payload: {
        name: 'renode',
        cwd,
      },
    });
  }

  public execMonitor(commands: string[]): Promise<any> {
    return this.sendSessionRequest({
      action: 'exec-monitor',
      payload: {
        commands,
      },
    });
  }

  public getUarts(machine: string): Promise<string[]> {
    return this.sendSessionRequest({
      action: 'exec-renode',
      payload: {
        command: 'uarts',
        args: { machine },
      },
    });
  }

  public getMachines(): Promise<string[]> {
    return this.sendSessionRequest({
      action: 'exec-renode',
      payload: {
        command: 'machines',
      },
    });
  }

  public async getSensors(
    machine: string,
    type?: SensorType,
  ): Promise<Sensor[]> {
    let sensorType = type === undefined ? {} : { type };
    let result = await this.sendSessionRequest({
      action: 'exec-renode',
      payload: {
        command: 'sensors',
        args: { machine, ...sensorType },
      },
    });
    return result.map(
      (entry: { name: string; types: string[] }) =>
        new Sensor(
          machine,
          entry.name,
          entry.types.map(type => SensorTypeFromString(type)!),
        ),
    );
  }

  public async getSensorValue(
    sensor: Sensor,
    type: SensorType,
  ): Promise<SensorValue> {
    const result = await this.sendSessionRequest({
      action: 'exec-renode',
      payload: {
        command: 'sensor-get',
        args: { machine: sensor.machine, peripheral: sensor.name, type },
      },
    });
    return GetSensorValue(type, result);
  }

  public setSensorValue(
    sensor: Sensor,
    type: SensorType,
    value: SensorValue,
  ): Promise<void> {
    return this.sendSessionRequest({
      action: 'exec-renode',
      payload: {
        command: 'sensor-set',
        args: {
          machine: sensor.machine,
          peripheral: sensor.name,
          type,
          value: value.sample,
        },
      },
    });
  }

  public async stopRenode(): Promise<void> {
    await this.sendSessionRequestTyped(
      {
        action: 'kill',
        payload: {
          name: 'renode',
        },
      },
      s.KillResponse,
    );
  }

  public async downloadZipToFs(zipUrl: string) {
    return this.sendSessionRequestTyped(
      {
        action: 'fs/zip',
        payload: {
          args: [zipUrl],
        },
      },
      s.FsZipResponse,
    );
  }

  public async downloadFile(path: string): Promise<Uint8Array> {
    const encoded = await this.sendSessionRequestTyped(
      {
        action: 'fs/dwnl',
        payload: {
          args: [path],
        },
      },
      s.FsDwnlResponse,
    );
    return Buffer.from(encoded, 'base64');
  }

  public async createDirectory(path: string): Promise<void> {
    await this.sendSessionRequestTyped(
      {
        action: 'fs/mkdir',
        payload: {
          args: [path],
        },
      },
      s.FsMkdirResponse,
    );
  }

  public sendFile(path: string, contents: Uint8Array) {
    const buf = Buffer.from(contents);
    const enc = buf.toString('base64');
    return this.sendSessionRequestTyped(
      {
        action: 'fs/upld',
        payload: {
          args: [path],
          data: enc,
        },
      },
      s.FsUpldResponse,
    );
  }

  public async listFiles(path: string) {
    return this.sendSessionRequestTyped(
      {
        action: 'fs/list',
        payload: {
          args: [path],
        },
      },
      s.FsListResponse,
    );
  }

  public statFile(path: string) {
    return this.sendSessionRequestTyped(
      {
        action: 'fs/stat',
        payload: {
          args: [path],
        },
      },
      s.FsStatResponse,
    );
  }

  public removeFile(path: string) {
    return this.sendSessionRequestTyped(
      {
        action: 'fs/remove',
        payload: {
          args: [path],
        },
      },
      s.FsRemoveResponse,
    );
  }

  public moveFile(from: string, to: string) {
    return this.sendSessionRequestTyped(
      {
        action: 'fs/move',
        payload: { args: [from, to] },
      },
      s.FsMoveResponse,
    );
  }

  public copyFile(from: string, to: string) {
    return this.sendSessionRequestTyped(
      {
        action: 'fs/copy',
        payload: { args: [from, to] },
      },
      s.FsCopyResponse,
    );
  }

  public dispose() {
    this.sessionSocket.close();
  }

  // *** Event handlers ***

  private onData(data: string) {
    this.requestQueue.shift()?.(data);
  }

  private onError() {
    this.requestQueue.shift()?.(undefined, new Error('WebSocket error'));
  }

  private onClose() {
    while (this.requestQueue.length) {
      this.requestQueue.shift()?.(undefined, new Error('WebSocket closed'));
    }

    this.dispatchEvent(new SocketClosedEvent());
  }

  // *** Utilities ***

  private async sendSessionRequestTyped<Res extends s.Response>(
    req: PartialRequest,
    resParser: z.ZodType<Res, any, object>,
  ): Promise<ResData<Res>> {
    const msg = {
      ...req,
      version: '0.0.1',
    };

    if (this.socketReady) {
      const res = await this.sendInner(JSON.stringify(msg));
      const resObj = JSON.parse(res);
      const resParsed = await resParser.safeParseAsync(resObj);

      if (!resParsed.success) {
        throw resParsed.error;
      }

      const obj = resParsed.data as Res;
      if (obj.status !== 'success') {
        throw new Error(obj.error);
      }

      return obj.data;
    } else {
      throw new Error('Not connected');
    }
  }

  private async sendSessionRequest(req: {
    action: string;
    payload?: { [key: string]: any };
  }): Promise<any> {
    const msg = {
      ...req,
      version: '0.0.1',
    };

    if (this.socketReady) {
      const res = await this.sendInner(JSON.stringify(msg));
      const obj: any = tryJsonParse(res);
      console.log('[DEBUG] got answer from session', obj);

      if (!obj?.status || obj.status !== 'success') {
        throw new Error(obj.error);
      }

      return obj.data;
    } else {
      throw new Error('Not connected');
    }
  }

  private sendInner(msg: string): Promise<string> {
    return new Promise(async (resolve, reject) => {
      console.log('[DEBUG] sending message to session', msg);

      if (this.sessionSocket) {
        this.requestQueue.push((res, err) => {
          if (err) {
            reject(err);
          } else {
            resolve(res);
          }
        });
        this.sessionSocket.send(msg);
      } else {
        reject(new Error('Not connected'));
      }
    });
  }
}

interface PartialRequest {
  action: string;
  [key: string]: any;
}

// Helper to properly type response payload
type ResData<T> = T extends { status: 'success'; data?: infer U } ? U : never;

type RequestCallback = (response: any, error?: any) => void;
