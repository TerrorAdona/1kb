import { create } from "zustand";
import { setAccessToken } from "../../shared/api/tokenMemory";
import { refreshAccessToken } from "../../shared/api/client";
import type { User } from "../../shared/types/api";
import {
  getCurrentUser,
  loginAccount,
  logoutAccount,
  registerAccount,
  updateCurrentUser,
} from "./authApi";

interface AuthState {
  user: User | null;
  initialized: boolean;
  initializing: boolean;
  initialize: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (payload: {
    email: string;
    display_name: string;
    password: string;
  }) => Promise<void>;
  signOut: () => Promise<void>;
  updateDisplayName: (displayName: string) => Promise<void>;
}

let initialization: Promise<void> | null = null;

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  initialized: false,
  initializing: false,

  initialize: async () => {
    if (get().initialized) return;
    if (!initialization) {
      set({ initializing: true });
      initialization = (async () => {
        try {
          await refreshAccessToken();
          const user = await getCurrentUser();
          set({ user });
        } catch {
          setAccessToken(null);
          set({ user: null });
        } finally {
          set({ initialized: true, initializing: false });
          initialization = null;
        }
      })();
    }
    await initialization;
  },

  signIn: async (email, password) => {
    const session = await loginAccount(email, password);
    setAccessToken(session.access);
    set({ user: session.user });
  },

  signUp: async (payload) => {
    await registerAccount(payload);
    const session = await loginAccount(payload.email, payload.password);
    setAccessToken(session.access);
    set({ user: session.user });
  },

  signOut: async () => {
    try {
      await logoutAccount();
    } finally {
      setAccessToken(null);
      set({ user: null });
    }
  },

  updateDisplayName: async (displayName) => {
    const user = await updateCurrentUser(displayName);
    set({ user });
  },
}));
