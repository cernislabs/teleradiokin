import { Component, OnInit, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { AuthService } from './core/auth.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  template: '<router-outlet />',
})
export class AppComponent implements OnInit {
  private readonly auth = inject(AuthService);

  ngOnInit(): void {
    // Hydrate the current user (and their role) app-wide when a token exists.
    if (this.auth.isAuthenticated() && !this.auth.user()) {
      this.auth.loadCurrentUser().subscribe({ error: () => this.auth.logout() });
    }
  }
}
