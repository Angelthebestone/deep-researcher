"use client";

import { useEffect } from "react";

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 text-foreground">
      <div className="text-center">
        <h1 className="mb-4 text-2xl font-bold tracking-tight">
          Algo salió mal
        </h1>
        <p className="mb-8 text-muted-foreground">
          Ocurrió un error inesperado. Puedes intentarlo de nuevo.
        </p>
        <button
          onClick={reset}
          className="inline-flex items-center justify-center rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
        >
          Intentar de nuevo
        </button>

        <details className="mt-8 w-full max-w-lg rounded-lg border border-border bg-card p-4 text-left">
          <summary className="cursor-pointer text-sm font-medium text-card-foreground">
            Detalles del error
          </summary>
          <div className="mt-3 space-y-2">
            <p className="text-xs text-muted-foreground">
              <span className="font-semibold">Mensaje:</span> {error.message}
            </p>
            {error.digest && (
              <p className="text-xs text-muted-foreground">
                <span className="font-semibold">Digest:</span> {error.digest}
              </p>
            )}
            {error.stack && (
              <pre className="mt-2 max-h-64 overflow-auto rounded-md bg-muted p-3 text-xs text-muted-foreground">
                {error.stack}
              </pre>
            )}
          </div>
        </details>
      </div>
    </div>
  );
}
