import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { DomSanitizer, SafeUrl } from '@angular/platform-browser';

import { StudyService } from '../../core/study.service';
import { Study } from '../../core/models';

@Component({
  selector: 'app-worklist',
  standalone: true,
  imports: [RouterLink, DatePipe],
  templateUrl: './worklist.component.html',
  styleUrl: './worklist.component.scss',
})
export class WorklistComponent implements OnInit {
  private readonly studyService = inject(StudyService);
  private readonly sanitizer = inject(DomSanitizer);

  readonly studies = signal<Study[]>([]);
  readonly previews = signal<Record<string, SafeUrl>>({});
  readonly loading = signal(true);

  ngOnInit(): void {
    this.studyService.worklist('Pending').subscribe({
      next: (list) => {
        this.studies.set(list);
        this.loading.set(false);
        for (const s of list) {
          if (s.has_preview) {
            this.loadPreview(s.id);
          }
        }
      },
      error: () => this.loading.set(false),
    });
  }

  private loadPreview(studyId: string): void {
    this.studyService.getPreviewBlob(studyId).subscribe((blob) => {
      const url = this.sanitizer.bypassSecurityTrustUrl(URL.createObjectURL(blob));
      this.previews.update((map) => ({ ...map, [studyId]: url }));
    });
  }
}
