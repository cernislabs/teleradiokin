import { Injectable, computed, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';

import { API_BASE } from './api.config';
import { Token, User, UserRole } from './models';

const TOKEN_KEY = 'teleradiokin.token';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly _token = signal<string | null>(localStorage.getItem(TOKEN_KEY));
  private readonly _user = signal<User | null>(null);

  readonly user = this._user.asReadonly();
  readonly isAuthenticated = computed(() => this._token() !== null);

  constructor(private readonly http: HttpClient) {}

  get token(): string | null {
    return this._token();
  }

  login(email: string, password: string): Observable<Token> {
    return this.http.post<Token>(`${API_BASE}/auth/login`, { email, password }).pipe(
      tap((res) => this.setToken(res.access_token)),
    );
  }

  loadCurrentUser(): Observable<User> {
    return this.http.get<User>(`${API_BASE}/auth/me`).pipe(tap((u) => this._user.set(u)));
  }

  hasRole(...roles: UserRole[]): boolean {
    const u = this._user();
    return u !== null && roles.includes(u.role);
  }

  logout(): void {
    this._token.set(null);
    this._user.set(null);
    localStorage.removeItem(TOKEN_KEY);
  }

  private setToken(token: string): void {
    this._token.set(token);
    localStorage.setItem(TOKEN_KEY, token);
  }
}
