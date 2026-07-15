const DEFAULT_API_URL = "http://127.0.0.1:8000";

export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? DEFAULT_API_URL;
}

type ApiErrorBody = {
  detail?: string | Array<{ msg?: string } | string>;
};

export async function downloadDefaultTemplate(): Promise<void> {
  const response = await fetch(`${getApiBaseUrl()}/api/default-template`);

  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }

  const blob = await response.blob();
  triggerBrowserDownload(blob, "default-template.docx");
}

export async function generateProposal(
  resources: File[],
  template: File | null,
): Promise<void> {
  const formData = new FormData();

  for (const file of resources) {
    formData.append("resources", file);
  }

  if (template) {
    formData.append("template", template);
  }

  const response = await fetch(`${getApiBaseUrl()}/api/generate`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }

  const blob = await response.blob();
  triggerBrowserDownload(blob, "proposal.docx");
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as ApiErrorBody;
    if (typeof data.detail === "string" && data.detail.trim()) {
      return data.detail;
    }
    if (Array.isArray(data.detail)) {
      const messages = data.detail
        .map((item) => {
          if (typeof item === "string") return item;
          if (item && typeof item.msg === "string") return item.msg;
          return null;
        })
        .filter((item): item is string => Boolean(item));
      if (messages.length > 0) {
        return messages.join(" — ");
      }
    }
  } catch {
    // Non-JSON error body
  }

  return `حدث خطأ في الخادم (${response.status})`;
}

function triggerBrowserDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
