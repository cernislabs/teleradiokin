import { Routes } from '@angular/router';

import { authGuard } from './core/auth.guard';
import { DashboardComponent } from './features/dashboard/dashboard.component';
import { LoginComponent } from './features/login/login.component';
import { PatientDetailComponent } from './features/patients/patient-detail.component';
import { PatientFormComponent } from './features/patients/patient-form.component';
import { PatientListComponent } from './features/patients/patient-list.component';
import { WorklistComponent } from './features/worklist/worklist.component';

export const routes: Routes = [
  { path: 'login', component: LoginComponent },
  { path: '', component: DashboardComponent, canActivate: [authGuard] },
  { path: 'patients', component: PatientListComponent, canActivate: [authGuard] },
  { path: 'patients/new', component: PatientFormComponent, canActivate: [authGuard] },
  { path: 'patients/:id', component: PatientDetailComponent, canActivate: [authGuard] },
  { path: 'worklist', component: WorklistComponent, canActivate: [authGuard] },
  {
    path: 'audit',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/audit/audit-log.component').then((m) => m.AuditLogComponent),
  },
  {
    // Lazy-loaded so the cornerstone viewer libraries stay out of the initial bundle.
    path: 'studies/:id/view',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/studies/viewer.component').then((m) => m.ViewerComponent),
  },
  { path: '**', redirectTo: '' },
];
