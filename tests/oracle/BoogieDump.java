import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.zip.GZIPInputStream;

import org.mitre.tdp.boogie.arinc.ArincRecord;
import org.mitre.tdp.boogie.arinc.ArincRecordParser;
import org.mitre.tdp.boogie.arinc.ArincVersion;
import org.mitre.tdp.boogie.arinc.RecordField;
import org.mitre.tdp.boogie.arinc.RecordSpec;

public class BoogieDump {
  public static void main(String[] args) throws Exception {
    if (args.length < 2) {
      System.err.println("Usage: BoogieDump <FAACIFP18(.gz)> <out.jsonl> [V18|V19|V20|V21|V22]");
      System.exit(2);
    }

    String inPath = args[0];
    String outPath = args[1];
    ArincVersion version = args.length >= 3 ? ArincVersion.valueOf(args[2]) : ArincVersion.V19;

    List<RecordSpec> specs = version.specs();
    Map<RecordSpec, ArincRecordParser> parsers = new LinkedHashMap<>();
    for (RecordSpec spec : specs) {
      parsers.put(spec, ArincRecordParser.standard(spec));
    }

    long total = 0;
    long matched = 0;
    Map<String, Long> counts = new LinkedHashMap<>();

    try (InputStream rawIn = new FileInputStream(inPath);
         InputStream in = inPath.endsWith(".gz") ? new GZIPInputStream(rawIn) : rawIn;
         BufferedReader reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.ISO_8859_1));
         BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(outPath), StandardCharsets.UTF_8))) {

      String line;
      while ((line = reader.readLine()) != null) {
        total++;
        for (RecordSpec spec : specs) {
          if (!spec.matchesRecord(line)) {
            continue;
          }
          String specName = spec.getClass().getSimpleName();
          Optional<ArincRecord> parsedOpt;
          try {
            parsedOpt = parsers.get(spec).parse(line);
          } catch (RuntimeException e) {
            counts.merge(specName + ":ERROR", 1L, Long::sum);
            break;
          }
          if (parsedOpt.isEmpty()) {
            break;
          }
          ArincRecord rec = parsedOpt.get();
          matched++;
          counts.merge(specName, 1L, Long::sum);

          StringBuilder sb = new StringBuilder(1024);
          sb.append("{\"line_no\":").append(total)
            .append(",\"spec\":\"").append(escape(specName)).append('"')
            .append(",\"fields\":{");
          boolean first = true;
          for (RecordField<?> rf : spec.recordFields()) {
            String fname = rf.fieldName();
            if ("BlankSpec".equals(rf.fieldSpec().getClass().getSimpleName())) {
              continue;
            }
            if (!first) {
              sb.append(',');
            }
            first = false;
            sb.append('"').append(escape(fname)).append("\":");
            Optional<?> val = rec.optionalField(fname);
            if (val.isEmpty()) {
              sb.append("null");
            } else {
              appendJson(sb, val.get());
            }
          }
          sb.append("}}\n");
          writer.write(sb.toString());
          break;
        }
      }
    }

    System.out.println("Total lines: " + total + ", matched by boogie " + version + ": " + matched);
    counts.forEach((k, v) -> System.out.println("  " + k + ": " + v));
  }

  private static void appendJson(StringBuilder sb, Object v) {
    if (v == null) {
      sb.append("null");
    } else if (v instanceof Boolean || v instanceof Integer || v instanceof Long) {
      sb.append(v);
    } else if (v instanceof Double d) {
      if (Double.isNaN(d) || Double.isInfinite(d)) {
        sb.append("null");
      } else if (d == 0.0) {
        sb.append("0.0");
      } else {
        sb.append(d);
      }
    } else if (v instanceof Enum<?> e) {
      sb.append('"').append(escape(e.name())).append('"');
    } else if (v instanceof Iterable<?> it) {
      sb.append('[');
      boolean first = true;
      for (Object item : it) {
        if (!first) sb.append(',');
        first = false;
        appendJson(sb, item);
      }
      sb.append(']');
    } else {
      sb.append('"').append(escape(v.toString())).append('"');
    }
  }

  private static String escape(String s) {
    StringBuilder out = new StringBuilder(s.length() + 8);
    for (int i = 0; i < s.length(); i++) {
      char c = s.charAt(i);
      switch (c) {
        case '"' -> out.append("\\\"");
        case '\\' -> out.append("\\\\");
        case '\n' -> out.append("\\n");
        case '\r' -> out.append("\\r");
        case '\t' -> out.append("\\t");
        default -> {
          if (c < 0x20) {
            out.append(String.format("\\u%04x", (int) c));
          } else {
            out.append(c);
          }
        }
      }
    }
    return out.toString();
  }
}
