import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { API_BASE } from './api.config';
import { Report, ReportStatus } from './models';

@Injectable({ providedIn: 'root' })
export class ReportService {
  private readonly http = inject(HttpClient);

  getForStudy(studyId: string): Observable<Report[]> {
    return this.http.get<Report[]>(`${API_BASE}/reports`, {
      params: { study_id: studyId },
    });
  }

  create(studyId: string, findings: string, impression: string, status: ReportStatus): Observable<Report> {
    return this.http.post<Report>(`${API_BASE}/reports`, {
      study_id: studyId,
      findings,
      impression,
      status,
    });
  }

  update(
    reportId: string,
    patch: { findings?: string; impression?: string; status?: ReportStatus },
  ): Observable<Report> {
    return this.http.patch<Report>(`${API_BASE}/reports/${reportId}`, patch);
  }

  getPdfBlob(reportId: string): Observable<Blob> {
    return this.http.get(`${API_BASE}/reports/${reportId}/pdf`, { responseType: 'blob' });
  }
}
