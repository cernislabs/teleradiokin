import { Component, OnInit, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { AuthService } from '../../core/auth.service';
import { AuditService } from '../../core/audit.service';
import { AuditAction, AuditEntity, AuditEvent } from '../../core/models';

@Component({
  selector: 'app-audit-log',
  standalone: true,
  imports: [RouterLink, DatePipe, FormsModule],
  templateUrl: './audit-log.component.html',
  styleUrl: './audit-log.component.scss',
})
export class AuditLogComponent implements OnInit {
  private readonly audit = inject(AuditService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  readonly events = signal<AuditEvent[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);

  readonly action = signal<AuditAction | ''>('');
  readonly entity = signal<AuditEntity | ''>('');

  readonly actions: AuditAction[] = ['login', 'view', 'create', 'update', 'finalize', 'download'];
  readonly entities: AuditEntity[] = ['session', 'patient', 'study', 'report'];

  ngOnInit(): void {
    // Admin-only view; hydrate the user after a refresh, then gate access.
    if (!this.auth.user()) {
      this.auth.loadCurrentUser().subscribe({
        next: () => this.guardAndLoad(),
        error: () => this.router.navigate(['/login']),
      });
    } else {
      this.guardAndLoad();
    }
  }

  private guardAndLoad(): void {
    if (!this.auth.hasRole('Admin')) {
      this.router.navigate(['/']);
      return;
    }
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.audit
      .list({
        action: this.action() || undefined,
        entity_type: this.entity() || undefined,
      })
      .subscribe({
        next: (list) => {
          this.events.set(list);
          this.loading.set(false);
        },
        error: () => {
          this.error.set('Could not load the audit trail.');
          this.loading.set(false);
        },
      });
  }

  summarize(detail: Record<string, unknown> | null): string {
    if (!detail) return '';
    return Object.entries(detail)
      .map(([k, v]) => `${k}: ${v}`)
      .join(', ');
  }
}
