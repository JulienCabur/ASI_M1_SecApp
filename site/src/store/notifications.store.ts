import { create } from 'zustand';
import type { Notification, NotificationStatus } from '@/types';

interface NotificationsStoreState {
  notifications: Notification[];
  pendingCount: number;
  setNotifications: (list: Notification[]) => void;
  resolve: (id: string, decision: NotificationStatus) => void;
}

const countPending = (list: Notification[]) =>
  list.filter((n) => n.status === 'pending').length;

export const useNotificationsStore = create<NotificationsStoreState>((set) => ({
  notifications: [],
  pendingCount: 0,

  setNotifications: (list) =>
    set({
      notifications: list,
      pendingCount: countPending(list),
    }),

  resolve: (id, decision) =>
    set((state) => {
      const updated = state.notifications.map((n) =>
        n.id === id ? { ...n, status: decision } : n
      );
      return {
        notifications: updated,
        pendingCount: countPending(updated),
      };
    }),
}));
