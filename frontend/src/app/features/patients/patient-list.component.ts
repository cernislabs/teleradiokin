import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { AuthService } from '../../core/auth.service';
import { PatientService } from '../../core/patient.service';
import { Patient } from '../../core/models';

@Component({
  selector: 'app-patient-list',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './patient-list.component.html',
  styleUrl: './patients.scss',
})
export class PatientListComponent implements OnInit {
  private readonly patients = inject(PatientService);
  private readonly auth = inject(AuthService);

  readonly items = signal<Patient[]>([]);
  readonly loading = signal(true);

  readonly canWrite = () => this.auth.hasRole('Admin', 'ReferringClinician');

  ngOnInit(): void {
    this.patients.list().subscribe({
      next: (list) => {
        this.items.set(list);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }
}
