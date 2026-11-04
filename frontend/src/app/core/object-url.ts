/**
 * Tracks object URLs created from blobs so they can be revoked together,
 * preventing the blob-memory leak that comes from calling
 * `URL.createObjectURL` without a matching `revokeObjectURL`.
 */
export class ObjectUrls {
  private urls: string[] = [];

  create(blob: Blob): string {
    const url = URL.createObjectURL(blob);
    this.urls.push(url);
    return url;
  }

  revokeAll(): void {
    for (const url of this.urls) {
      URL.revokeObjectURL(url);
    }
    this.urls = [];
  }
}
