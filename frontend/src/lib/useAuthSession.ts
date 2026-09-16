import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getSession, logout as logoutRequest } from "../api/client";

export function useAuthSession() {
  return useQuery({ queryKey: ["auth-session"], queryFn: getSession });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return async () => {
    const result = await logoutRequest();
    queryClient.setQueryData(["auth-session"], result);
  };
}
