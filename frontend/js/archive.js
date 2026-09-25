// Unpacks DMARC report files in the browser: plain .xml, gzip (.xml.gz, .gz) and .zip (stored or deflated entries).
// Nothing is uploaded; the format is recognised by its magic bytes, the extension only decides what we try to open.
import { t } from "./i18n.js";

const MAX_XML_BYTES = 100 * 1024 * 1024; // cap on one unpacked report (zip bombs)
const decoder = new TextDecoder("utf-8");

class ArchiveError extends Error {}

function concat(chunks, total) {
  const out = new Uint8Array(total);
  let pos = 0;
  chunks.forEach((c) => {
    out.set(c, pos);
    pos += c.length;
  });
  return out;
}

async function inflate(bytes, format) {
  if (typeof DecompressionStream === "undefined") throw new ArchiveError(t("dmarc.err_no_unpack"));
  try {
    const reader = new Blob([bytes]).stream().pipeThrough(new DecompressionStream(format)).getReader();
    const chunks = [];
    let total = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.length;
      if (total > MAX_XML_BYTES) {
        await reader.cancel();
        throw new ArchiveError(t("dmarc.err_too_large"));
      }
      chunks.push(value);
    }
    return decoder.decode(concat(chunks, total));
  } catch (err) {
    throw err instanceof ArchiveError ? err : new ArchiveError(t("dmarc.err_archive"));
  }
}

// Reads the central directory (so entries written with a data descriptor work too) and unpacks every .xml entry.
async function unzip(bytes, zipName) {
  const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let eocd = -1;
  for (let i = bytes.length - 22; i >= Math.max(0, bytes.length - 22 - 65535); i--) {
    if (dv.getUint32(i, true) === 0x06054b50) {
      eocd = i;
      break;
    }
  }
  if (eocd < 0) throw new ArchiveError(t("dmarc.err_archive"));
  const count = dv.getUint16(eocd + 10, true);
  let p = dv.getUint32(eocd + 16, true);
  const reports = [];
  for (let n = 0; n < count; n++) {
    if (p + 46 > bytes.length || dv.getUint32(p, true) !== 0x02014b50) throw new ArchiveError(t("dmarc.err_archive"));
    const method = dv.getUint16(p + 10, true);
    const compSize = dv.getUint32(p + 20, true);
    const nameLen = dv.getUint16(p + 28, true);
    const extraLen = dv.getUint16(p + 30, true);
    const commentLen = dv.getUint16(p + 32, true);
    const localOffset = dv.getUint32(p + 42, true);
    const name = decoder.decode(bytes.subarray(p + 46, p + 46 + nameLen));
    p += 46 + nameLen + extraLen + commentLen;
    if (!/\.xml$/i.test(name) || name.startsWith("__MACOSX/")) continue;

    if (localOffset + 30 > bytes.length || dv.getUint32(localOffset, true) !== 0x04034b50) throw new ArchiveError(t("dmarc.err_archive"));
    const start = localOffset + 30 + dv.getUint16(localOffset + 26, true) + dv.getUint16(localOffset + 28, true);
    const data = bytes.subarray(start, start + compSize);
    let text;
    if (method === 0) {
      if (data.length > MAX_XML_BYTES) throw new ArchiveError(t("dmarc.err_too_large"));
      text = decoder.decode(data);
    } else if (method === 8) {
      text = await inflate(data, "deflate-raw");
    } else {
      throw new ArchiveError(t("dmarc.err_archive"));
    }
    reports.push({ name: `${zipName} > ${name}`, text });
  }
  if (!reports.length) throw new ArchiveError(t("dmarc.err_no_xml"));
  return reports;
}

// File -> [{name, text}] (a .zip can hold several reports).
export async function readReports(file) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  if (bytes[0] === 0x1f && bytes[1] === 0x8b) return [{ name: file.name, text: await inflate(bytes, "gzip") }];
  if (bytes[0] === 0x50 && bytes[1] === 0x4b) return unzip(bytes, file.name);
  if (/\.(gz|zip)$/i.test(file.name)) throw new ArchiveError(t("dmarc.err_archive"));
  return [{ name: file.name, text: decoder.decode(bytes) }];
}
