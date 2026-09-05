import { useEffect, useRef } from "react";

export function WorldMapBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    let frame = 0;
    let animationFrame = 0;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      canvas.style.width = `${window.innerWidth}px`;
      canvas.style.height = `${window.innerHeight}px`;
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = () => {
      const width = window.innerWidth;
      const height = window.innerHeight;
      context.clearRect(0, 0, width, height);

      const t = frame * 0.004;
      const points = [
        [0.18, 0.34], [0.27, 0.48], [0.37, 0.27], [0.47, 0.42],
        [0.56, 0.31], [0.67, 0.5], [0.76, 0.3], [0.84, 0.45],
      ];

      context.lineWidth = 1;
      context.strokeStyle = "rgba(80, 170, 255, 0.24)";
      context.fillStyle = "rgba(120, 200, 255, 0.38)";

      points.forEach(([x, y], index) => {
        const px = x * width;
        const py = y * height + Math.sin(t + index) * 4;
        context.beginPath();
        context.arc(px, py, 1.5, 0, Math.PI * 2);
        context.fill();

        if (index < points.length - 1) {
          const [nx, ny] = points[index + 1];
          context.beginPath();
          context.moveTo(px, py);
          context.lineTo(nx * width, ny * height + Math.sin(t + index + 1) * 4);
          context.stroke();
        }
      });

      frame += 1;
      animationFrame = requestAnimationFrame(draw);
    };

    resize();
    window.addEventListener("resize", resize);
    animationFrame = requestAnimationFrame(draw);

    return () => {
      window.removeEventListener("resize", resize);
      cancelAnimationFrame(animationFrame);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      style={{
        position: "fixed",
        inset: 0,
        width: "100vw",
        height: "100vh",
        pointerEvents: "none",
        zIndex: 0,
        opacity: 0.28,
      }}
    />
  );
}
