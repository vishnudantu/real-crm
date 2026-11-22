import { useQuery } from "@tanstack/react-query";
import { fetchProjects } from "../admin/api";
import type { ProjectListResponse } from "../admin/projectModel";

export function useInventoryProjects(): {
  projects: ProjectListResponse["items"];
  isLoading: boolean;
  isError: boolean;
  error: unknown;
} {
  const query = useQuery({
    queryKey: ["inventory", "projects"],
    queryFn: () => fetchProjects({ page: 1, pageSize: 100 }),
    staleTime: 60_000,
  });
  return {
    projects: query.data?.items ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
  };
}
