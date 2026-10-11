import React, { useState } from 'react';
import { GlyphArrowRight } from './AtelierGlyphs';

const EXAMPLES = [
  { label: 'Material', title: 'Start with your course material', description: 'Upload a supported document, image or lecture. Processing status appears in My Materials.', image: '/assets/chapter_source.jpg' },
  { label: 'Explanation', title: 'Read a clear explanation', description: 'Create a lesson from a topic or material that is ready. Keep the explanation and examples in one workspace.', image: '/assets/chapter_evidence.jpg' },
  { label: 'Connections', title: 'Explore how concepts connect', description: 'Generate a diagram when a visual view will help. Return to the same lesson to keep studying.', image: '/assets/chapter_knowledge.jpg' },
  { label: 'Video', title: 'Review with a narrated video', description: 'Request a video from your lesson. The workspace shows reported preparation states and plays the saved result.', image: '/assets/act4_learning_experience.jpg' },
  { label: 'Practice', title: 'Check your understanding', description: 'Request practice questions, submit your answers and review the returned score and feedback.', image: '/assets/chapter_mastery.jpg' },
  { label: 'Revision', title: 'Return to your saved work', description: 'Revisit notes and explanations, or ask a question about the same lesson.', image: '/assets/specimen_analog_notebook.jpg' }
];

export default function TransformationSpecimen() {
  const [selected, setSelected] = useState(0);
  const example = EXAMPLES[selected];
  return <section className="transformation-specimen-widget" aria-label="Illustrated product guide">
    <p className="demo-disclosure">Illustrated examples. These images are a product guide, not a live processing job or your saved results.</p>
    <div className="example-selector" aria-label="Choose an example">
      {EXAMPLES.map((item, index) => <button key={item.label} type="button" className="btn-atelier-outline" aria-pressed={selected === index} onClick={() => setSelected(index)}>{item.label}</button>)}
    </div>
    <div className="transformation-display-grid">
      <figure className="specimen-contained-card"><img src={example.image} alt={`${example.label} illustration`} className="specimen-plate-image" /><figcaption className="demo-disclosure">Illustration {selected + 1} of {EXAMPLES.length}</figcaption></figure>
      <div className="transformation-meta-column"><h3 className="transformation-stage-title">{example.title}</h3><p className="transformation-stage-desc">{example.description}</p><button type="button" className="btn-atelier-outline" onClick={() => setSelected((selected + 1) % EXAMPLES.length)}>Next example <GlyphArrowRight size={12} /></button></div>
    </div>
  </section>;
}
