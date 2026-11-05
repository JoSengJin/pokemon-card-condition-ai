import { z } from 'zod';

export const relPath = z.string().min(1).max(300)
  .refine((p) => !p.startsWith('/') && !p.split('/').includes('..') && !p.includes('\0') && !p.includes('\\'), '상대경로만 허용')
  .refine((p) => !/[*?[\]]/.test(p), 'glob은 허용하지 않음. 정확한 파일 또는 "디렉터리/"');

export const scopePath = relPath
  .refine((p) => p !== '.' && p !== './' && !p.startsWith('./') && !p.includes('//') && !p.includes('/./') && !p.endsWith('/.'),
    '정리되지 않은 경로: "./"·"."(저장소 전체)·"./docs/" 표기는 거부합니다. 정확한 파일 또는 "디렉터리/"만 쓰세요');
