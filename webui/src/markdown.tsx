// @ts-ignore marked is declared by package.json; this sandbox may not have it cached.
import { marked } from "marked";

const allowedTags = new Set([
  "A",
  "BLOCKQUOTE",
  "BR",
  "CODE",
  "EM",
  "H1",
  "H2",
  "H3",
  "H4",
  "HR",
  "LI",
  "OL",
  "P",
  "PRE",
  "SPAN",
  "STRONG",
  "UL",
]);

function escapeHtml(text: string): string {
  const chars: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  return text.replace(/[&<>"']/g, (ch) => chars[ch]);
}

export function sanitizeMarkdownHtml(html: string): string {
  const template = document.createElement("template");
  template.innerHTML = html;
  template.content.querySelectorAll("script,style").forEach((n) => n.remove());
  const clean = (el: Element) => {
    if (!allowedTags.has(el.tagName)) {
      el.replaceWith(...Array.from(el.childNodes));
      return;
    }
    for (const attr of Array.from(el.attributes)) {
      const name = attr.name.toLowerCase();
      const value = attr.value.trim();
      const safeHref = name === "href" && /^(https?:|mailto:|#|\/(?!\/))/i.test(value);
      const safeWiki = el.tagName === "SPAN" && name === "class" && value === "talamus-wikilink";
      if (name.startsWith("on") || (!safeHref && name !== "title" && !safeWiki)) el.removeAttribute(attr.name);
    }
    el.querySelectorAll("*").forEach((child) => clean(child));
  };
  template.content.querySelectorAll("*").forEach((el) => clean(el));
  return template.innerHTML;
}

function wikilinks(text: string): string {
  return text.replace(/\[\[([^\]]+)\]\]/g, (_m, label: string) => `<span class="talamus-wikilink">${escapeHtml(label)}</span>`);
}

export function Markdown({ text }: { text: string }) {
  const raw = marked.parse(wikilinks(text || ""), { async: false, gfm: true, breaks: false }) as string;
  const html = sanitizeMarkdownHtml(raw);
  return (
    <>
      <style>{`
        .talamus-markdown { color: var(--text); font-size: 13.5px; line-height: 1.65; word-break: break-word; }
        .talamus-markdown > :first-child { margin-top: 0; }
        .talamus-markdown > :last-child { margin-bottom: 0; }
        .talamus-markdown h1 { font-size: 20px; line-height: 1.25; margin: 0 0 12px; }
        .talamus-markdown h2 { font-size: 17px; line-height: 1.3; margin: 18px 0 8px; }
        .talamus-markdown h3, .talamus-markdown h4 { font-size: 14px; line-height: 1.35; margin: 14px 0 6px; }
        .talamus-markdown p, .talamus-markdown ul, .talamus-markdown ol, .talamus-markdown blockquote { margin: 0 0 10px; }
        .talamus-markdown ul, .talamus-markdown ol { padding-left: 20px; }
        .talamus-markdown code { background: var(--surface-2); border: 1px solid var(--border); border-radius: 4px; padding: 1px 4px; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 12.5px; }
        .talamus-markdown pre { background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--r-sm); padding: 10px; overflow: auto; }
        .talamus-markdown pre code { border: 0; padding: 0; background: transparent; }
        .talamus-markdown a, .talamus-markdown .talamus-wikilink { color: var(--accent-2); }
      `}</style>
      <div className="talamus-markdown" dangerouslySetInnerHTML={{ __html: html }} />
    </>
  );
}
