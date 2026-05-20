import type { Publication } from "./types";

/**
 * KIPRIS / Google Patents 외부 링크 URL 빌드.
 *
 * Google Patents는 한국 특허 앞 '10' 접두어를 제외한 번호 사용.
 * ex) 1020240168054 → KR20240168054A
 */
export function buildPatentLinks(pub: Publication): {
  kiprisUrl: string;
  googlePatentsUrl: string;
} {
  const appNumClean = pub.application_number.replace(/-/g, "");
  const patentIdClean = pub.patent_id?.replace(/-/g, "") || "";
  const patentIdForGoogle = patentIdClean.startsWith("10")
    ? patentIdClean.slice(2)
    : patentIdClean;
  return {
    kiprisUrl: `https://doi.org/10.8080/${appNumClean}`,
    googlePatentsUrl: `https://patents.google.com/patent/KR${patentIdForGoogle}A`,
  };
}
