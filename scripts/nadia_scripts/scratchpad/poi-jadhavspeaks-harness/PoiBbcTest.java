package bbc;

import static org.junit.jupiter.api.Assertions.assertNotNull;

import com.filecomparator.model.FileContent;
import com.filecomparator.parser.ExcelParser;
import java.io.File;
import java.io.FileOutputStream;
import java.util.Random;
import org.apache.poi.ss.usermodel.Cell;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.ss.usermodel.Workbook;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.junit.jupiter.api.Test;

/**
 * BBC differential for the POI 5 IOUtils byte-array cap, exercising the client's REAL
 * production path: {@link ExcelParser#parse(String)} -> WorkbookFactory.create(InputStream).
 *
 * The fixture is an .xlsx whose sharedStrings.xml exceeds POI 5's default 100,000,000-byte
 * cap, built from DISTINCT, INCOMPRESSIBLE strings so that (a) shared-string dedup does not
 * shrink it and (b) the zip inflate-ratio (zip-bomb) guard is not tripped first.
 *
 * Uses only API present in both POI 4.1.2 and 5.2.5 (no setByteArrayMaxOverride in the test;
 * that override lives in production code = the adaptation).
 *
 * Expected: PASS on 4.1.2 (no cap) -> FAIL on 5.2.5 parent (RecordFormatException) ->
 * PASS on 5.2.5 adapted (production override raises the cap).
 */
public class PoiBbcTest {

    @Test
    public void reproducesBbc() throws Exception {
        File xlsx = File.createTempFile("bbc-poi-bytecap", ".xlsx");
        xlsx.deleteOnExit();

        // ~135 MB of distinct, incompressible shared-string text (4500 x 30000 chars).
        Random rnd = new Random(12345);
        try (Workbook wb = new XSSFWorkbook()) {
            Sheet sheet = wb.createSheet("s");
            for (int r = 0; r < 4500; r++) {
                char[] buf = new char[30000];
                for (int i = 0; i < buf.length; i++) buf[i] = (char) ('a' + rnd.nextInt(26));
                Row row = sheet.createRow(r);
                Cell cell = row.createCell(0);
                cell.setCellValue(new String(buf));
            }
            try (FileOutputStream out = new FileOutputStream(xlsx)) {
                wb.write(out);
            }
        }

        // Real production entry point — the byte-cap manifests inside WorkbookFactory.create.
        FileContent content = new ExcelParser().parse(xlsx.getAbsolutePath());
        assertNotNull(content, "parse() returned null / threw — POI byte-cap not handled");
    }
}
