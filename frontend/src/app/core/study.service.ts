import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, firstValueFrom } from 'rxjs';

import { API_BASE } from './api.config';
import { Study, UploadSession } from './models';

const CHUNK_SIZE = 2 * 1024 * 1024; // 2 MiB — friendly to low-bandwidth links.

@Injectable({ providedIn: 'root' })
export class StudyService {
  private readonly http = inject(HttpClient);

  listForPatient(patientId: string): Observable<Study[]> {
    return this.http.get<Study[]>(`${API_BASE}/studies`, {
      params: { patient_id: patientId },
    });
  }

  previewUrl(studyId: string): string {
    return `${API_BASE}/studies/${studyId}/preview`;
  }

  /** Fetch the preview via HttpClient so the auth interceptor applies. */
  getPreviewBlob(studyId: string): Observable<Blob> {
    return this.http.get(`${API_BASE}/studies/${studyId}/preview`, {
      responseType: 'blob',
    });
  }

  /**
   * Resumable chunked upload: open a session, send the file in chunks (resuming
   * from the server's reported offset on retry), then complete.
   * `onProgress` receives a 0–1 fraction.
   */
  async upload(
    file: File,
    encounterId: string,
    onProgress?: (fraction: number) => void,
  ): Promise<Study> {
    const session = await firstValueFrom(
      this.http.post<UploadSession>(`${API_BASE}/studies/uploads`, {
        encounter_id: encounterId,
        filename: file.name,
        content_type: file.type || 'application/octet-stream',
        total_size: file.size,
      }),
    );

    let offset = session.received_bytes;
    while (offset < file.size) {
      const end = Math.min(offset + CHUNK_SIZE, file.size);
      const chunk = file.slice(offset, end);
      const updated = await firstValueFrom(
        this.http.put<UploadSession>(
          `${API_BASE}/studies/uploads/${session.id}?offset=${offset}`,
          chunk,
        ),
      );
      offset = updated.received_bytes;
      onProgress?.(offset / file.size);
    }

    return firstValueFrom(
      this.http.post<Study>(`${API_BASE}/studies/uploads/${session.id}/complete`, {}),
    );
  }
}
