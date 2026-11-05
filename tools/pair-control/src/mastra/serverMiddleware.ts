import { validator } from 'hono/validator';
import { ALLOWED_HOSTS, ALLOWED_ORIGINS } from './serverContext.ts';
import { validateRequest } from './requestPolicy.ts';

export const requestGuard = validator('header', (_headers, c) => validateRequest(c, ALLOWED_HOSTS, ALLOWED_ORIGINS));
