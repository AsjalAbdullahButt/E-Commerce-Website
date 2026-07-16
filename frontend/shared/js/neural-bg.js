// === NEURAL-BG.JS ===
// Canvas animation background

document.addEventListener('DOMContentLoaded', () => {
  const canvas = document.getElementById('neural-bg');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  let width = canvas.width = window.innerWidth;
  let height = canvas.height = window.innerHeight;

  // Read the live --gold design token instead of a hardcoded color, so the
  // background always matches whatever the theme currently defines.
  const goldHex = getComputedStyle(document.documentElement).getPropertyValue('--gold').trim() || '#FFD700';
  const goldRgb = hexToRgb(goldHex);
  const strokeColor = `rgba(${goldRgb}, 0.3)`;
  const fillColor = `rgba(${goldRgb}, 0.5)`;

  function hexToRgb(hex) {
    const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return m ? `${parseInt(m[1], 16)}, ${parseInt(m[2], 16)}, ${parseInt(m[3], 16)}` : '255, 215, 0';
  }

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const nodes = [];
  const nodeCount = Math.floor(Math.sqrt(width * height / 10000));

  // Create nodes
  for (let i = 0; i < nodeCount; i++) {
    nodes.push({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.5,
      vy: (Math.random() - 0.5) * 0.5
    });
  }

  function draw() {
    ctx.clearRect(0, 0, width, height);
    ctx.strokeStyle = strokeColor;
    ctx.fillStyle = fillColor;

    // Update and draw nodes
    nodes.forEach(node => {
      node.x += node.vx;
      node.y += node.vy;

      // Bounce off walls
      if (node.x < 0 || node.x > width) node.vx *= -1;
      if (node.y < 0 || node.y > height) node.vy *= -1;

      // Keep in bounds
      node.x = Math.max(0, Math.min(width, node.x));
      node.y = Math.max(0, Math.min(height, node.y));

      ctx.beginPath();
      ctx.arc(node.x, node.y, 1.5, 0, Math.PI * 2);
      ctx.fill();
    });

    // Draw connections
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < 150) {
          ctx.beginPath();
          ctx.moveTo(nodes[i].x, nodes[i].y);
          ctx.lineTo(nodes[j].x, nodes[j].y);
          ctx.stroke();
        }
      }
    }

    if (!reducedMotion) requestAnimationFrame(draw);
  }

  window.addEventListener('resize', () => {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  });

  // Motion-safe: render one static frame instead of an endless particle drift.
  if (reducedMotion) {
    nodes.forEach(node => { node.vx = 0; node.vy = 0; });
  }

  draw();
});
