// Copyright (c) 2025 Antmicro <www.antmicro.com>
//
// SPDX-License-Identifier: Apache-2.0

export const UartOpened = 'uart-opened';
export const RenodeQuitted = 'renode-quitted';

export interface UartOpenedArgs {
  port: number;
  name: string;
  machineName: string;
}
export type UartOpenedCallback = (event: UartOpenedArgs) => void;
