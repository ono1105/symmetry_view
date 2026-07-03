  const threeStatus = document.querySelector("[data-three-status]");
  async function loadThreeView() {
    if (threeStatus) threeStatus.textContent = "Loading Three.js core…";
    await import("/vendor/three/three.module.js");
    if (threeStatus) threeStatus.textContent = "Loading Three.js controls…";
    await import("/vendor/three/addons/controls/TrackballControls.js");
    if (threeStatus) threeStatus.textContent = "Loading Three.js view…";
    await import("/static/three_view.js");
  }
  loadThreeView().catch(error => {
    const stage = threeStatus ? threeStatus.textContent : "Three.js module";
    if (threeStatus) threeStatus.textContent = `${stage} error: ${error.message}`;
    console.error("Three.js module load failed", error);
  });
