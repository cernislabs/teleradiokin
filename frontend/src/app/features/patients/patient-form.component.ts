import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { PatientService } from '../../core/patient.service';
import { AdministrativeGender } from '../../core/models';

@Component({
  selector: 'app-patient-form',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './patient-form.component.html',
  styleUrl: './patients.scss',
})
export class PatientFormComponent {
  private readonly fb = inject(FormBuilder);
  private readonly patients = inject(PatientService);
  private readonly router = inject(Router);

  readonly submitting = signal(false);
  readonly error = signal<string | null>(null);

  readonly sexes: AdministrativeGender[] = ['male', 'female', 'other', 'unknown'];

  readonly form = this.fb.nonNullable.group({
    mrn: ['', [Validators.required]],
    family_name: ['', [Validators.required]],
    given_name: ['', [Validators.required]],
    birth_date: [''],
    sex: ['unknown' as AdministrativeGender, [Validators.required]],
    phone: [''],
    consent_acknowledged: [false, [Validators.requiredTrue]],
  });

  submit(): void {
    if (this.form.invalid || this.submitting()) {
      return;
    }
    this.submitting.set(true);
    this.error.set(null);

    const v = this.form.getRawValue();
    this.patients
      .create({
        mrn: v.mrn,
        family_name: v.family_name,
        given_name: v.given_name,
        birth_date: v.birth_date || null,
        sex: v.sex,
        phone: v.phone || null,
        consent_acknowledged: v.consent_acknowledged,
      })
      .subscribe({
        next: (p) => this.router.navigate(['/patients', p.id]),
        error: (err) => {
          this.submitting.set(false);
          this.error.set(
            err?.status === 409
              ? $localize`:@@patients.form.duplicate:A patient with this MRN already exists.`
              : $localize`:@@patients.form.error:Could not create the patient. Please check the fields.`,
          );
        },
      });
  }
}
