"use client";

import { useEffect, useRef, useState } from "react";

export type AnimationSceneName =
  | "hero"
  | "pdf"
  | "chunks"
  | "embedding"
  | "vector"
  | "search"
  | "answer"
  | "vault";

const sceneNames: Record<AnimationSceneName, string> = {
  hero: "hero-constellation",
  pdf: "scene-pdf",
  chunks: "scene-chunks",
  embedding: "scene-embedding",
  vector: "scene-vector",
  search: "scene-search",
  answer: "scene-answer",
  vault: "scene-vault",
};

function SceneArtwork({ scene }: { scene: AnimationSceneName }) {
  if (scene === "hero") {
    return (
      <>
        <svg className="scene-svg hero-constellation-svg" viewBox="0 0 360 250">
          <g className="constellation-lines" fill="none" stroke="currentColor">
            <path d="M56 75 113 52 159 99 218 63 286 91M83 171l76-72 60 79 67-87" />
            <path d="m113 52 105 11m-59 36 68 51m-143 21-27-96" />
          </g>
          <g className="constellation-dots">
            <circle cx="56" cy="75" r="3" /><circle cx="113" cy="52" r="4" />
            <circle cx="159" cy="99" r="5" /><circle cx="218" cy="63" r="3" />
            <circle cx="286" cy="91" r="4" /><circle cx="83" cy="171" r="3" />
            <circle cx="218" cy="178" r="4" /><circle cx="285" cy="91" r="2" />
            <circle cx="244" cy="142" r="3" /><circle cx="130" cy="154" r="2" />
          </g>
          <circle className="search-pulse" cx="159" cy="99" r="18" />
        </svg>
        <span className="hero-demo-question">Example question · “What is machine learning?”</span>
        <span className="hero-demo-answer">Example answer <span aria-hidden="true">[1]</span></span>
      </>
    );
  }

  if (scene === "vault") {
    return (
      <svg className="scene-svg" viewBox="0 0 220 92">
        <g className="vault-group">
          <path d="M14 34h54v45H14zM25 34v-9a16 16 0 0 1 32 0v9" />
          <circle cx="41" cy="53" r="4" /><path d="M41 57v8" />
        </g>
        <g className="vault-group vault-group-second">
          <path d="M84 34h54v45H84zM95 34v-9a16 16 0 0 1 32 0v9" />
          <circle cx="111" cy="53" r="4" /><path d="M111 57v8" />
        </g>
        <g className="vault-group vault-group-third">
          <path d="M154 34h54v45h-54zM165 34v-9a16 16 0 0 1 32 0v9" />
          <circle cx="181" cy="53" r="4" /><path d="M181 57v8" />
        </g>
      </svg>
    );
  }

  return (
    <svg className="scene-svg pipeline-svg" viewBox="0 0 160 100">
      {scene === "pdf" && (
        <g className="scene-shape">
          <path d="M48 13h42l23 23v51H48z" />
          <path d="M90 13v24h23M60 51h40M60 62h40M60 73h28" />
          <path className="scene-accent" d="M58 44h43" />
        </g>
      )}
      {scene === "chunks" && (
        <g className="scene-shape">
          <path d="M25 19h110v18H25zM25 43h72v18H25zM25 67h91v18H25z" />
          <path className="scene-accent chunk-split" d="M73 40v24M105 64v24" />
        </g>
      )}
      {scene === "embedding" && (
        <g className="scene-shape">
          <path d="M20 24h120v52H20z" />
          <path d="M33 42h18m8 0h8m8 0h14m8 0h9m8 0h16M33 59h9m8 0h17m8 0h9m8 0h17m8 0h12" />
          <circle className="vector-dot" cx="46" cy="42" r="3" />
          <circle className="vector-dot vector-dot-second" cx="106" cy="59" r="3" />
        </g>
      )}
      {scene === "vector" && (
        <g className="scene-shape">
          <path d="M27 77 68 21l38 56z" />
          <circle cx="27" cy="77" r="5" /><circle cx="68" cy="21" r="5" />
          <circle cx="106" cy="77" r="5" /><circle className="vector-dot" cx="77" cy="55" r="7" />
        </g>
      )}
      {scene === "search" && (
        <g className="scene-shape">
          <circle cx="70" cy="44" r="25" />
          <path d="m88 62 20 20" />
          <circle className="scene-accent search-wave" cx="70" cy="44" r="37" />
          <circle className="vector-dot" cx="46" cy="35" r="3" />
          <circle className="vector-dot" cx="94" cy="40" r="3" />
        </g>
      )}
      {scene === "answer" && (
        <g className="scene-shape">
          <path d="M23 20h114v60H23z" />
          <path d="M36 35h77M36 47h66M36 59h52" />
          <rect className="scene-accent" x="96" y="62" width="27" height="12" rx="4" />
          <path d="M102 68h14" />
        </g>
      )}
    </svg>
  );
}

export function AnimationScene({ scene }: { scene: AnimationSceneName }) {
  const sceneRef = useRef<HTMLDivElement>(null);
  const [inViewport, setInViewport] = useState(false);
  const [pageVisible, setPageVisible] = useState(true);

  useEffect(() => {
    const element = sceneRef.current;
    if (!element || !("IntersectionObserver" in window)) return;

    const observer = new IntersectionObserver(
      ([entry]) => setInViewport(entry.isIntersecting),
      { threshold: 0.15 },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const updateVisibility = () => setPageVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", updateVisibility);
    updateVisibility();
    return () => document.removeEventListener("visibilitychange", updateVisibility);
  }, []);

  return (
    <div
      aria-hidden="true"
      className={`animation-scene ${sceneNames[scene]}`}
      data-active={inViewport && pageVisible ? "true" : "false"}
      ref={sceneRef}
    >
      <SceneArtwork scene={scene} />
    </div>
  );
}
