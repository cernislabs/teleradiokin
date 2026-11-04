import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { API_BASE } from './api.config';
import { AuditAction, AuditEntity, AuditEvent } from './models';

export interface AuditFilters {
  action?: AuditAction;
  entity_type?: AuditEntity;
  limit?: number;
}

@Injectable({ providedIn: 'root' })
export class AuditService {
  private readonly http = inject(HttpClient);

  list(filters: AuditFilters = {}): Observable<AuditEvent[]> {
    let params = new HttpParams();
    if (filters.action) params = params.set('action', filters.action);
    if (filters.entity_type) params = params.set('entity_type', filters.entity_type);
    params = params.set('limit', String(filters.limit ?? 200));
    return this.http.get<AuditEvent[]>(`${API_BASE}/audit`, { params });
  }
}
