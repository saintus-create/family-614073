import Image from "next/image";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { compileMDX } from "next-mdx-remote/rsc";
import remarkGfm from "remark-gfm";
import { allSlugs, readPage } from "@/lib/pages";

export const dynamicParams = false;

export function generateStaticParams() {
  return [{ slug: [] }, ...allSlugs().map((slug) => ({ slug: slug.split("/") }))];
}

async function render(slug: string) {
  const page = readPage(slug);
  if (!page) notFound();
  const { content, frontmatter } = await compileMDX<{
    title?: string;
    subtitle?: string;
  }>({
    source: page.source,
    options: {
      parseFrontmatter: true,
      mdxOptions: {
        remarkPlugins: [remarkGfm],
      },
    },
  });
  return { content, frontmatter };
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug?: string[] }>;
}): Promise<Metadata> {
  const { slug = [] } = await params;
  const key = slug.length === 0 ? "welcome" : slug.join("/");
  const { frontmatter } = await render(key);
  return {
    title: frontmatter.title || "Clinical Evidence Index",
    description: frontmatter.subtitle,
  };
}

export default async function MdxPage({
  params,
}: {
  params: Promise<{ slug?: string[] }>;
}) {
  const { slug = [] } = await params;
  const key = slug.length === 0 ? "welcome" : slug.join("/");
  const { content, frontmatter } = await render(key);

  return (
    <div className="flex flex-col flex-1 items-center justify-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex flex-1 w-full max-w-3xl flex-col items-center justify-between py-32 px-16 bg-white dark:bg-black sm:items-start">
        <a href="/">
          <Image
            className="dark:invert"
            src="/next.svg"
            alt="Next.js logo"
            width={100}
            height={20}
            priority
          />
        </a>
        <div className="flex flex-col items-center gap-6 text-center sm:items-start sm:text-left">
          <h1 className="max-w-xs text-3xl font-semibold leading-10 tracking-tight text-black dark:text-zinc-50">
            {frontmatter.title || "Clinical Evidence Index"}
          </h1>
          {frontmatter.subtitle && (
            <p className="max-w-md text-lg leading-8 text-zinc-600 dark:text-zinc-400">
              {frontmatter.subtitle}
            </p>
          )}
        </div>
        <div className="w-full max-w-md text-lg leading-8 text-zinc-600 dark:text-zinc-400 [&_a]:font-medium [&_a]:text-zinc-950 dark:[&_a]:text-zinc-50 [&_h2]:mt-8 [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:leading-8 [&_h2]:text-black dark:[&_h2]:text-zinc-50 [&_h3]:mt-6 [&_h3]:text-base [&_h3]:font-semibold [&_h3]:leading-7 [&_h3]:text-black dark:[&_h3]:text-zinc-50 [&_p]:mt-3 [&_ul]:mt-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:mt-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:mt-2 [&_table]:mt-4 [&_table]:w-full [&_table]:text-sm [&_th]:pr-4 [&_th]:text-left [&_th]:font-medium [&_td]:pr-4 [&_td]:align-top [&_blockquote]:mt-4 [&_blockquote]:border-l [&_blockquote]:border-black/[.08] [&_blockquote]:pl-4 dark:[&_blockquote]:border-white/[.145]">
          {content}
        </div>
        <div className="flex flex-col gap-4 text-base font-medium sm:flex-row">
          <a
            className="flex h-12 w-full items-center justify-center gap-2 rounded-full bg-foreground px-5 text-background transition-colors hover:bg-[#383838] dark:hover:bg-[#ccc] md:w-[158px]"
            href="/medications"
          >
            Meds
          </a>
          <a
            className="flex h-12 w-full items-center justify-center rounded-full border border-solid border-black/[.08] px-5 transition-colors hover:border-transparent hover:bg-black/[.04] dark:border-white/[.145] dark:hover:bg-[#1a1a1a] md:w-[158px]"
            href="/cencal-health/prior-authorization"
          >
            CenCal
          </a>
        </div>
      </main>
    </div>
  );
}
