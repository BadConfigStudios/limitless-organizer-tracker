import { useMutation, useQueryClient } from "@tanstack/react-query";
import { triggerTask } from "../api/client";

const RESUBMIT_ENDPOINT = "/api/tasks/resubmit-application";

export function ResubmitNowButton() {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => triggerTask(RESUBMIT_ENDPOINT),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["resubmissions"] });
      queryClient.invalidateQueries({ queryKey: ["resubmissions-summary"] });
      queryClient.invalidateQueries({ queryKey: ["status-history"] });
    },
  });

  return (
    <div>
      <button
        type="button"
        className={`btn btn-primary btn-sm ${mutation.isPending ? "btn-disabled" : ""}`}
        disabled={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        Resubmit Now
      </button>
      {mutation.isSuccess && (
        <p className="text-success text-sm mt-2">Resubmission triggered successfully</p>
      )}
      {mutation.isError && (
        <p className="text-error text-sm mt-2">Failed to trigger resubmission</p>
      )}
    </div>
  );
}
