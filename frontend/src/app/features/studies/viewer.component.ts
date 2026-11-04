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
import { DomSanitizer, SafeUrl } from '@angular/platform-browser';

import { CornerstoneService } from '../../core/cornerstone.service';
import { StudyService } from '../../core/study.service';
import { Study } from '../../core/models';

type Tool = 'wwwc' | 'pan' | 'zoom';

@Component({
  selector: 'app-viewer',
  standalone: true,
  imports: [RouterLink, DatePipe],
  templateUrl: './viewer.component.html',
  styleUrl: './viewer.component.scss',
})
export class ViewerComponent implements AfterViewInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly studyService = inject(StudyService);
  private readonly cornerstone = inject(CornerstoneService);
  private readonly sanitizer = inject(DomSanitizer);

  @ViewChild('viewport') viewportRef!: ElementRef<HTMLElement>;

  readonly study = signal<Study | null>(null);
  readonly imageUrl = signal<SafeUrl | null>(null);
  readonly error = signal<string | null>(null);
  readonly activeTool = signal<Tool>('wwwc');

  isDicom = () => this.study()?.is_dicom === true;

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
