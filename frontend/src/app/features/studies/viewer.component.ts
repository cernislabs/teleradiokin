import {
  AfterViewInit,
  Component,
  ElementRef,
  OnDestroy,
  ViewChild,
  inject,
  signal,
} from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeUrl } from '@angular/platform-browser';

import { AuthService } from '../../core/auth.service';
import { CornerstoneService } from '../../core/cornerstone.service';
import { ReportService } from '../../core/report.service';
import { StudyService } from '../../core/study.service';
import { Report, Study } from '../../core/models';

type Tool = 'wwwc' | 'pan' | 'zoom';

@Component({
  selector: 'app-viewer',
  standalone: true,
  imports: [RouterLink, DatePipe, FormsModule],
  templateUrl: './viewer.component.html',
  styleUrl: './viewer.component.scss',
})
export class ViewerComponent implements AfterViewInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly studyService = inject(StudyService);
  private readonly reportService = inject(ReportService);
  private readonly auth = inject(AuthService);
  private readonly cornerstone = inject(CornerstoneService);
  private readonly sanitizer = inject(DomSanitizer);

  @ViewChild('viewport') viewportRef!: ElementRef<HTMLElement>;

  readonly study = signal<Study | null>(null);
  readonly imageUrl = signal<SafeUrl | null>(null);
  readonly error = signal<string | null>(null);
  readonly activeTool = signal<Tool>('wwwc');

  // --- Report state ---
  readonly report = signal<Report | null>(null);
  readonly findings = signal('');
  readonly impression = signal('');
  readonly reportSaving = signal(false);
  readonly reportMsg = signal<string | null>(null);

  isDicom = () => this.study()?.is_dicom === true;

  canAuthor = () =>
    this.auth.hasRole('Radiologist', 'Admin') &&
    (this.report() === null || this.report()!.status === 'Draft');

  isFinal = () => this.report()?.status === 'Final';

  private enabled = false;
  private dragging = false;
  private lastX = 0;
  private lastY = 0;

  ngAfterViewInit(): void {
    const id = this.route.snapshot.paramMap.get('id') ?? '';
    this.studyService.get(id).subscribe((s) => {
      this.study.set(s);
      this.studyService.getFileBlob(id).subscribe({
        next: (blob) => this.render(blob),
        error: () => this.error.set($localize`:@@viewer.error:Could not load the study image.`),
      });
    });
    this.loadReport(id);
  }

  private loadReport(studyId: string): void {
    this.reportService.getForStudy(studyId).subscribe((list) => {
      const r = list[0] ?? null;
      this.report.set(r);
      if (r) {
        this.findings.set(r.findings);
        this.impression.set(r.impression);
      }
    });
  }

  private persist(status: 'Draft' | 'Final'): void {
    const study = this.study();
    if (!study || this.reportSaving()) {
      return;
    }
    this.reportSaving.set(true);
    this.reportMsg.set(null);
    const existing = this.report();
    const done = {
      next: (r: Report) => {
        this.report.set(r);
        this.reportSaving.set(false);
        this.reportMsg.set(
          status === 'Final'
            ? $localize`:@@report.finalized:Report finalized.`
            : $localize`:@@report.saved:Draft saved.`,
        );
      },
      error: () => {
        this.reportSaving.set(false);
        this.reportMsg.set($localize`:@@report.error:Could not save the report.`);
      },
    };
    if (existing) {
      this.reportService
        .update(existing.id, { findings: this.findings(), impression: this.impression(), status })
        .subscribe(done);
    } else {
      this.reportService
        .create(study.id, this.findings(), this.impression(), status)
        .subscribe(done);
    }
  }

  saveDraft(): void {
    this.persist('Draft');
  }

  finalize(): void {
    this.persist('Final');
  }

  openPdf(): void {
    const r = this.report();
    if (!r) {
      return;
    }
    this.reportService.getPdfBlob(r.id).subscribe((blob) => {
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
    });
  }

  private render(blob: Blob): void {
    if (this.isDicom()) {
      const el = this.viewportRef.nativeElement;
      this.cornerstone.enable(el);
      this.enabled = true;
      this.cornerstone
        .display(el, blob)
        .catch(() => this.error.set($localize`:@@viewer.decodeError:Could not decode this DICOM image.`));
    } else {
      this.imageUrl.set(this.sanitizer.bypassSecurityTrustUrl(URL.createObjectURL(blob)));
    }
  }

  setTool(tool: Tool): void {
    this.activeTool.set(tool);
  }

  reset(): void {
    if (this.enabled) {
      this.cornerstone.reset(this.viewportRef.nativeElement);
    }
  }

  onMouseDown(event: MouseEvent): void {
    if (!this.enabled) {
      return;
    }
    this.dragging = true;
    this.lastX = event.clientX;
    this.lastY = event.clientY;
    event.preventDefault();
  }

  onMouseMove(event: MouseEvent): void {
    if (!this.enabled || !this.dragging) {
      return;
    }
    const el = this.viewportRef.nativeElement;
    const dx = event.clientX - this.lastX;
    const dy = event.clientY - this.lastY;
    this.lastX = event.clientX;
    this.lastY = event.clientY;

    const vp = this.cornerstone.getViewport(el);
    const tool = this.activeTool();
    if (tool === 'wwwc') {
      vp.voi.windowWidth = Math.max(1, vp.voi.windowWidth + dx);
      vp.voi.windowCenter = vp.voi.windowCenter + dy;
    } else if (tool === 'pan') {
      vp.translation.x += dx / vp.scale;
      vp.translation.y += dy / vp.scale;
    } else {
      vp.scale = Math.max(0.05, vp.scale - dy * 0.01);
    }
    this.cornerstone.setViewport(el, vp);
  }

  onMouseUp(): void {
    this.dragging = false;
  }

  onWheel(event: WheelEvent): void {
    if (!this.enabled) {
      return;
    }
    event.preventDefault();
    const el = this.viewportRef.nativeElement;
    const vp = this.cornerstone.getViewport(el);
    vp.scale = Math.max(0.05, vp.scale + (event.deltaY < 0 ? 0.15 : -0.15));
    this.cornerstone.setViewport(el, vp);
  }

  ngOnDestroy(): void {
    if (this.enabled && this.viewportRef) {
      this.cornerstone.disable(this.viewportRef.nativeElement);
    }
  }
}
