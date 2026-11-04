import { staticRoutes } from './routesStatic.ts';
import { taskLifecycleRoutes } from './routesTasksLifecycle.ts';
import { taskDecisionRoutes } from './routesTaskDecisions.ts';
import { taskAdminRoutes } from './routesTaskAdmin.ts';
import { taskRuntimeRoutes } from './routesTaskRuntime.ts';
import { taskFinishRoutes } from './routesTaskFinish.ts';
import { taskInspectRoutes } from './routesTaskInspect.ts';
import { mainRoutes } from './routesMain.ts';
import { pushRoutes } from './routesPush.ts';
import { systemRoutes } from './routesSystem.ts';

export const routes = [...staticRoutes, ...taskLifecycleRoutes, ...taskDecisionRoutes, ...taskAdminRoutes, ...taskRuntimeRoutes, ...taskFinishRoutes, ...taskInspectRoutes, ...mainRoutes, ...pushRoutes, ...systemRoutes];
