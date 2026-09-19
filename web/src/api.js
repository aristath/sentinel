export async function getJson(path, { signal } = {}) {
  const response = await fetch(path, {
    headers: { Accept: "application/json" },
    signal,
  });

  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }

  return response.json();
}

async function mutationJson(path, method, body, { signal } = {}) {
  const response = await fetch(path, {
    method,
    headers: {
      Accept: "application/json",
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    signal,
  });
  const payload = await response.json().catch(() => undefined);

  if (!response.ok) {
    throw new Error(
      payload?.detail ?? `${response.status} ${response.statusText}`,
    );
  }

  return payload;
}

export function putJson(path, body, options) {
  return mutationJson(path, "PUT", body, options);
}

export function postJson(path, body, options) {
  return mutationJson(path, "POST", body, options);
}

export function deleteJson(path, options) {
  return mutationJson(path, "DELETE", undefined, options);
}

export async function postEventStream(path, body, onEvent, { signal } = {}) {
  const response = await fetch(path, {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => undefined);
    throw new Error(
      payload?.detail ?? `${response.status} ${response.statusText}`,
    );
  }
  if (!response.body) throw new Error("Chat stream has no response body");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder
        .decode(value, { stream: !done })
        .replace(/\r\n/g, "\n");
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        const data = frame
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trimStart())
          .join("\n");
        if (data) await onEvent(JSON.parse(data));
      }
      if (done) break;
    }
  } catch (error) {
    await reader.cancel().catch(() => {});
    throw error;
  } finally {
    reader.releaseLock();
  }
}
