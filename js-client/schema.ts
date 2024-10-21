// Copyright (c) 2024 Antmicro <www.antmicro.com>
//
// SPDX-License-Identifier: Apache-2.0

import { z, ZodRawShape } from 'zod';

export const BaseResponse = z.object({
  version: z.literal('0.0.1'),
  status: z.string(),
});
export const OkResponse = BaseResponse.extend({
  status: z.literal('success'),
  data: z.any(),
});
export type OkResponse = z.infer<typeof OkResponse>;
export const ErrorResponse = BaseResponse.extend({
  status: z.literal('failure'),
  error: z.string().default('Unknown error'),
});
export type ErrorResponse = z.infer<typeof ErrorResponse>;
export const Response = OkResponse.or(ErrorResponse);
export type Response = z.infer<typeof Response>;

function resp<T extends ZodRawShape>(obj: T) {
  return OkResponse.extend(obj).or(ErrorResponse);
}

export const KillResponse = resp({
  data: z.object({}),
});
export type KillResponse = z.infer<typeof KillResponse>;

export const FsListResponse = resp({
  data: z
    .object({
      name: z.string(),
      isfile: z.boolean(),
      islink: z.boolean(),
    })
    .array(),
});
export type FsListResponse = z.infer<typeof FsListResponse>;

export const FsStatResponse = resp({
  data: z.object({
    size: z.number(),
    isfile: z.boolean(),
    ctime: z.number(),
    mtime: z.number(),
  }),
});
export type FsStatResponse = z.infer<typeof FsStatResponse>;

export const FsDwnlResponse = resp({
  data: z.string().base64(),
});
export type FsDwnlResponse = z.infer<typeof FsDwnlResponse>;

export const FsUpldResponse = resp({
  data: z.object({
    path: z.string(),
  }),
});
export type FsUpldResponse = z.infer<typeof FsUpldResponse>;

export const FsRemoveResponse = resp({
  data: z.object({
    path: z.string(),
  }),
});
export type FsRemoveResponse = z.infer<typeof FsRemoveResponse>;

export const FsMkdirResponse = resp({
  data: z.object({}),
});
export type FsMkdirResponse = z.infer<typeof FsMkdirResponse>;

export const FsZipResponse = resp({
  data: z.object({
    path: z.string(),
  }),
});
export type FsZipResponse = z.infer<typeof FsZipResponse>;

export const FsMoveResponse = resp({
  data: z.object({
    from: z.string(),
    to: z.string(),
  }),
});
export type FsMoveResponse = z.infer<typeof FsMoveResponse>;

export const FsCopyResponse = resp({
  data: z.object({
    from: z.string(),
    to: z.string(),
  }),
});
export type FsCopyResponse = z.infer<typeof FsCopyResponse>;
