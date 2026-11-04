import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { DatePipe } from '@angular/common';
import { DomSanitizer, SafeUrl } from '@angular/platform-browser';

import { AuthService } from '../../core/auth.service';
import { PatientService } from '../../core/patient.service';
import { StudyService } from '../../core/study.service';
import { ObjectUrls } from '../../core/object-url';
import { Encounter, Patient, Study } from '../../core/models';

@Component({
  selector: 'app-patient-detail',
  standalone: true,
  imports: [RouterLink, FormsModule, DatePipe],
  templateUrl: './patient-detail.component.html',
  styleUrl: './patients.scss',
})
export class PatientDetailComponent implements OnInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly patients = inject(PatientService);
  private readonly studyService = inject(StudyService);
  private readonly auth = inject(AuthService);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly objectUrls = new ObjectUrls();

  readonly patient = signal<Patient | null>(null);
  readonly encounters = signal<Encounter[]>([]);
  readonly studies = signal<Study[]>([]);
  readonly previews = signal<Record<string, SafeUrl>>({});

  readonly selectedEncounter = signal('');
  readonly uploading = signal(false);
  readonly progress = signal(0);
  readonly uploadError = signal<string | null>(null);

  readonly canWrite = () => this.auth.hasRole('Admin', 'ReferringClinician');

  private patientId = '';

  ngOnInit(): void {
    this.patientId = this.route.snapshot.paramMap.get('id') ?? '';
    this.patients.get(this.patientId).subscribe((p) => this.patient.set(p));
    this.reloadEncounters();
    this.reloadStudies();
  }

  reloadEncounters(): void {
    this.patients.listEncounters(this.patientId).subscribe((e) => {
      this.encounters.set(e);
      if (!this.selectedEncounter() && e.length) {
        this.selectedEncounter.set(e[0].id);
      }
    });
  }

  reloadStudies(): void {
    this.studyService.listForPatient(this.patientId).subscribe((list) => {
      this.studies.set(list);
      for (const s of list) {
        if (s.has_preview && !this.previews()[s.id]) {
          this.loadPreview(s.id);
        }
      }
    });
  }

  private loadPreview(studyId: string): void {
    this.studyService.getPreviewBlob(studyId).subscribe((blob) => {
      const url = this.sanitizer.bypassSecurityTrustUrl(this.objectUrls.create(blob));
      this.previews.update((map) => ({ ...map, [studyId]: url }));
    });
  }

  ngOnDestroy(): void {
    this.objectUrls.revokeAll();
  }

  addEncounter(reason: string): void {
    const trimmed = reason.trim();
    if (!trimmed) {
      return;
    }
    this.patients.createEncounter(this.patientId, trimmed).subscribe(() => this.reloadEncounters());
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    const encounterId = this.selectedEncounter();
    if (!file || !encounterId) {
      return;
    }
    this.uploading.set(true);
    this.progress.set(0);
    this.uploadError.set(null);

    this.studyService
      .upload(file, encounterId, (f) => this.progress.set(Math.round(f * 100)))
      .then(() => {
        this.uploading.set(false);
        input.value = '';
        this.reloadStudies();
      })
      .catch(() => {
        this.uploading.set(false);
        this.uploadError.set($localize`:@@studies.upload.error:Upload failed. Please retry.`);
      });
  }
}
