const runtimeStatus = document.querySelector("#runtime-status");

async function initialiseShell() {
  const response = await fetch("/api/config", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Configuration request failed: ${response.status}`);
  }

  const config = await response.json();
  document.title = `${config.product.name} | ${config.product.module}`;
  runtimeStatus.textContent =
    `Local modules staged: Three.js ${config.runtime.three.version}. ` +
    "3D interaction is scheduled for Task 5.";
}

initialiseShell().catch(() => {
  runtimeStatus.textContent =
    "Local runtime configuration unavailable. No simulation has started.";
});
