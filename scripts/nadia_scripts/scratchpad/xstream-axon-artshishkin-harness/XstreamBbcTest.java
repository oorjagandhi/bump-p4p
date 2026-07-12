package bbc;

import static org.junit.Assert.assertEquals;

import com.thoughtworks.xstream.XStream;
import java.util.UUID;
import net.shyshkin.study.cqrs.estore.core.config.XStreamConfig;
import net.shyshkin.study.cqrs.estore.core.model.ProductIdDto;
import org.junit.Test;

/**
 * BBC differential for xstream 1.4.18 default-deny, exercising the REAL production
 * adaptation XStreamConfig.xStream() (allowTypesByWildcard "net.shyshkin...**").
 *
 * plainXStream()      = Axon's pre-adaptation default (plain new XStream(), no allowlist)
 * configuredXStream() = the production adaptation (XStreamConfig)
 *
 * At xstream 1.4.17 both PASS. At 1.4.18+ plainXStream FAILS (ForbiddenClassException
 * on ProductIdDto) while configuredXStream PASSES -> the adaptation resolves the break.
 */
public class XstreamBbcTest {

    private final ProductIdDto dto = new ProductIdDto(UUID.randomUUID());

    @Test
    public void plainXStream() {
        XStream x = new XStream();
        ProductIdDto back = (ProductIdDto) x.fromXML(x.toXML(dto));
        assertEquals(dto.getProductId(), back.getProductId());
    }

    @Test
    public void configuredXStream() {
        XStream x = new XStreamConfig().xStream();
        ProductIdDto back = (ProductIdDto) x.fromXML(x.toXML(dto));
        assertEquals(dto.getProductId(), back.getProductId());
    }
}
