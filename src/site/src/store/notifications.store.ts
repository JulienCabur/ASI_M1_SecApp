import { create } from 'zustand';
import type { Notification, NotificationStatus, PendingFileRequest } from '@/types';

interface NotificationsStoreState {
  notifications: Notification[];
  pendingCount: number;
  pendingFileCount: number;
  setNotifications: (list: Notification[]) => void;
  setFileRequests: (list: PendingFileRequest[]) => void;
  resolve: (id: string, decision: NotificationStatus) => void;
}

const countPending = (list: Notification[]) =>
  list.filter((n) => n.status === 'pending').length;

export const useNotificationsStore = create<NotificationsStoreState>((set) => ({
  notifications: [],
  pendingCount: 0,
  pendingFileCount: 0,

  setNotifications: (list) =>
    set({
      notifications: list,
      pendingCount: countPending(list),
    }),

  setFileRequests: (list) =>
    set({ pendingFileCount: list.length }),

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
