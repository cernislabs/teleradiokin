import { Injectable } from '@angular/core';
import * as cornerstone from 'cornerstone-core';
import * as cornerstoneWADOImageLoader from 'cornerstone-wado-image-loader';
import * as dicomParser from 'dicom-parser';

/**
 * Thin wrapper over cornerstone for single-study DICOM display.
 *
 * Web workers are disabled so no extra worker/codec assets need to be served;
 * uncompressed DICOM (the formats this MVP accepts and produces) decode on the
 * main thread. Compressed transfer syntaxes needing codecs are a documented
 * follow-up.
 */
@Injectable({ providedIn: 'root' })
export class CornerstoneService {
  private initialized = false;

  private init(): void {
    if (this.initialized) {
      return;
    }
    cornerstoneWADOImageLoader.external.cornerstone = cornerstone;
    cornerstoneWADOImageLoader.external.dicomParser = dicomParser;
    cornerstoneWADOImageLoader.configure({ useWebWorkers: false });
    this.initialized = true;
  }

  enable(element: HTMLElement): void {
    this.init();
    cornerstone.enable(element);
  }

  disable(element: HTMLElement): void {
    try {
      cornerstone.disable(element);
    } catch {
      /* element may already be disabled */
    }
  }

  async display(element: HTMLElement, blob: Blob): Promise<void> {
    this.init();
    const file = new File([blob], 'study.dcm');
    const imageId: string = cornerstoneWADOImageLoader.wadouri.fileManager.add(file);
    const image = await cornerstone.loadImage(imageId);
    cornerstone.displayImage(element, image);
    cornerstone.fitToWindow(element);
  }

  reset(element: HTMLElement): void {
    cornerstone.reset(element);
    cornerstone.fitToWindow(element);
  }

  getViewport(element: HTMLElement): any {
    return cornerstone.getViewport(element);
  }

  setViewport(element: HTMLElement, viewport: any): void {
    cornerstone.setViewport(element, viewport);
  }
}
