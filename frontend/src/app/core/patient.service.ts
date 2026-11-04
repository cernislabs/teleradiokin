import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { API_BASE } from './api.config';
import { Encounter, Patient, PatientCreate } from './models';

@Injectable({ providedIn: 'root' })
export class PatientService {
  private readonly http = inject(HttpClient);

  list(): Observable<Patient[]> {
    return this.http.get<Patient[]>(`${API_BASE}/patients`);
  }

  get(id: string): Observable<Patient> {
    return this.http.get<Patient>(`${API_BASE}/patients/${id}`);
  }

  create(patient: PatientCreate): Observable<Patient> {
    return this.http.post<Patient>(`${API_BASE}/patients`, patient);
  }

  listEncounters(patientId: string): Observable<Encounter[]> {
    return this.http.get<Encounter[]>(`${API_BASE}/encounters`, {
      params: { patient_id: patientId },
    });
  }

  createEncounter(patientId: string, reason: string): Observable<Encounter> {
    return this.http.post<Encounter>(`${API_BASE}/encounters`, {
      patient_id: patientId,
      reason,
    });
  }
}
