import Link from "next/link";
import { AnimationScene, type AnimationSceneName } from "@/components/animation-scene";

const steps: {
  scene: AnimationSceneName;
  title: string;
  description: string;
}[] = [
  {
    scene: "pdf",
    title: "Upload a PDF",
    description:
      "Add a document you want to explore. Your account is required to see and use your own documents.",
  },
  {
    scene: "chunks",
    title: "Extract and split the text",
    description:
      "The app reads selectable PDF text and divides it into smaller passages, keeping page information with each passage.",
  },
  {
    scene: "embedding",
    title: "Create embeddings",
    description:
      "Gemini turns each passage into a list of numbers, called an embedding, that represents aspects of its meaning.",
  },
  {
    scene: "vector",
    title: "Search with pgvector",
    description:
      "PostgreSQL and pgvector compare the question with your passages and return the closest matches for your account.",
  },
  {
    scene: "search",
    title: "Draft an answer",
    description:
      "Gemini receives the question and retrieved passages. The prompt asks it to answer from that context and say when it is insufficient.",
  },
  {
    scene: "answer",
    title: "Show the sources",
    description:
      "The answer can point to numbered passages. The API checks citation numbers against the passages actually retrieved.",
  },
];

const features = [
  {
    title: "PDF workspace",
    description:
      "Upload, review processing status, and manage documents from one account.",
  },
  {
    title: "Meaning-based search",
    description:
      "Find passages related to a question, even when the wording is not an exact match.",
  },
  {
    title: "Page-level citations",
    description:
      "Answers include references that connect back to retrieved document passages and page numbers.",
  },
  {
    title: "Private document scope",
    description:
      "API searches filter by the signed-in user so one account's document chunks are not returned to another.",
  },
];

export default function Home() {
  return (
    <main className="landing-page" id="main-content">
      <section aria-labelledby="hero-title" className="hero">
        <div>
          <p className="eyebrow">A calmer way to explore your PDFs</p>
          <h1 className="metallic-heading" id="hero-title">
            Find the useful pages in what you already know.
          </h1>
          <p className="hero-copy">
            Upload a PDF, ask a question in everyday language, and explore an
            answer with references to the passages it used.
          </p>
          <div className="hero-actions">
            <Link className="button-primary" href="/signup">
              Create an account
            </Link>
            <Link className="button-secondary" href="/login">
              Log in
            </Link>
          </div>
          <p className="hero-disclosure">
            Privacy note: text extracted from uploaded PDFs is sent to the
            Google Gemini API to create embeddings. When you ask a question,
            retrieved passages are also sent to Gemini to draft an answer.
          </p>
        </div>

        <aside
          aria-label="Illustrative answer preview"
          className="glass-panel glass-blur preview-card"
        >
          <AnimationScene scene="hero" />
          <span className="preview-label">Illustrative example — not real output</span>
          <p className="preview-question">Example question</p>
          <p className="preview-answer">
            “A machine-learning model finds patterns in examples and uses them
            to make predictions.” <span className="citation-pill">[1]</span>
          </p>
          <div className="preview-source">
            <span aria-hidden="true" className="source-mark">
              1
            </span>
            <span>
              <strong>Sample document</strong>
              <br />
              Page 4 · Example source passage
            </span>
          </div>
        </aside>
      </section>

      <section aria-labelledby="how-title" className="landing-section">
        <p className="eyebrow">From document to answer</p>
        <h2 className="section-heading metallic-heading" id="how-title">
          How it works
        </h2>
        <p className="section-intro">
          This pattern is called retrieval-augmented generation, or RAG. It
          finds relevant pieces of your documents first, then gives those pieces
          to a language model as context for a response.
        </p>
        <ol className="steps-grid">
          {steps.map((step, index) => (
            <li className="glass-panel step-card" key={step.title}>
              <AnimationScene scene={step.scene} />
              <span aria-hidden="true" className="step-number">
                {String(index + 1).padStart(2, "0")}
              </span>
              <h3>{step.title}</h3>
              <p>{step.description}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="trust-title" className="landing-section">
        <p className="eyebrow">Designed for grounded answers</p>
        <h2 className="section-heading metallic-heading" id="trust-title">
          Why answers are easier to check
        </h2>
        <p className="section-intro">
          These are safeguards in the app’s design, not a promise that a model
          can never make a mistake. Check the cited passages when accuracy
          matters.
        </p>
        <div className="trust-visual-row">
          <AnimationScene scene="vault" />
          <p className="helper-text">
            Illustration of account-scoped document access; it does not represent live user activity.
          </p>
        </div>
        <div className="trust-grid">
          <article className="glass-panel trust-card">
            <h3>Answers use retrieved context</h3>
            <p>
              The generation prompt asks Gemini to answer only from the
              retrieved passages and to say when that context is not enough.
            </p>
          </article>
          <article className="glass-panel trust-card">
            <h3>Citations are checked</h3>
            <p>
              The API keeps citations only when their numbers map to passages
              retrieved for that signed-in user.
            </p>
          </article>
          <article className="glass-panel trust-card">
            <h3>No-match questions are declined</h3>
            <p>
              When no passage meets the configured similarity threshold, the
              app returns a fixed not-found response without calling the chat
              generation model.
            </p>
          </article>
          <article className="glass-panel trust-card">
            <h3>Document search is user-scoped</h3>
            <p>
              Searches filter by the current account. The design is intended
              to keep each user’s document content private from other users of
              the app.
            </p>
          </article>
        </div>
      </section>

      <section aria-labelledby="features-title" className="landing-section">
        <p className="eyebrow">A focused workspace</p>
        <h2 className="section-heading metallic-heading" id="features-title">
          The tools to go from a file to a source
        </h2>
        <div className="feature-grid">
          {features.map((feature) => (
            <article className="glass-panel feature-card" key={feature.title}>
              <h3>{feature.title}</h3>
              <p>{feature.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section aria-labelledby="architecture-title" className="landing-section">
        <p className="eyebrow">A small, understandable stack</p>
        <h2 className="section-heading metallic-heading" id="architecture-title">
          How the pieces connect
        </h2>
        <div
          aria-label="Architecture overview"
          className="glass-panel architecture"
          role="group"
        >
          <div className="architecture-node">
            <strong>Browser</strong>
            <span>Next.js interface</span>
          </div>
          <span aria-hidden="true" className="architecture-arrow">→</span>
          <div className="architecture-node">
            <strong>FastAPI</strong>
            <span>Authentication and RAG</span>
          </div>
          <span aria-hidden="true" className="architecture-arrow">→</span>
          <div className="architecture-node">
            <strong>PostgreSQL</strong>
            <span>pgvector search</span>
          </div>
          <span aria-hidden="true" className="architecture-arrow">↔</span>
          <div className="architecture-node">
            <strong>Google Gemini</strong>
            <span>Embeddings and answers</span>
          </div>
        </div>
        <div className="tech-grid">
          <article className="glass-panel tech-card">
            <h3>Interface</h3>
            <p>Next.js App Router, React, TypeScript, and Tailwind CSS.</p>
          </article>
          <article className="glass-panel tech-card">
            <h3>Backend and data</h3>
            <p>FastAPI, SQLAlchemy, PostgreSQL, and pgvector.</p>
          </article>
          <article className="glass-panel tech-card">
            <h3>Language model</h3>
            <p>Google Gemini for document embeddings and cited answer drafts.</p>
          </article>
        </div>
      </section>

      <section aria-labelledby="limitations-title" className="landing-section">
        <p className="eyebrow">What to expect</p>
        <h2 className="section-heading metallic-heading" id="limitations-title">
          Honest limitations
        </h2>
        <ul className="limitation-list">
          <li>
            Each question is answered independently; conversations are not
            saved as chat history.
          </li>
          <li>
            Request limits apply. They currently live in one backend process,
            so they reset on restart and do not coordinate across servers.
          </li>
          <li>
            Answers depend on Gemini availability and may be unavailable when
            the provider is overloaded.
          </li>
          <li>
            Scanned PDFs without selectable text are not read with OCR.
          </li>
          <li>
            Retrieved passages and extracted PDF text are sent to Google
            Gemini for the AI features described above.
          </li>
        </ul>
      </section>

      <footer className="site-footer">
        <span>Built to make document sources easier to explore.</span>
        <a
          href="https://github.com/balajipodila/ai-knowledge-assistant"
          rel="noopener noreferrer"
          target="_blank"
        >
          View the project on GitHub
        </a>
      </footer>
    </main>
  );
}
