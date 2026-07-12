package bbc;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.chaintrade.core.model.ProductRestModel;
import com.thoughtworks.xstream.XStream;
import java.math.BigDecimal;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import productservice.config.EventProcessingConfig;

/**
 * BBC differential for xstream 1.4.18 default-deny, exercising the REAL production
 * adaptation EventProcessingConfig.xStream() (allowTypesByWildcard "com.chaintrade.core.**").
 *
 * plainXStream()      = Axon's pre-adaptation default (plain new XStream(), no allowlist)
 * configuredXStream() = the production adaptation (EventProcessingConfig @Bean)
 *
 * At xstream 1.4.17 both PASS. At 1.4.18+ plainXStream FAILS (ForbiddenClassException
 * on ProductRestModel) while configuredXStream PASSES -> the adaptation resolves the break.
 */
public class XstreamBbcTest {

    private final ProductRestModel dto =
            new ProductRestModel(UUID.randomUUID(), "widget", new BigDecimal("9.99"), 3);

    @Test
    void plainXStream() {
        XStream x = new XStream();
        ProductRestModel back = (ProductRestModel) x.fromXML(x.toXML(dto));
        assertEquals(dto.getProductId(), back.getProductId());
    }

    @Test
    void configuredXStream() {
        XStream x = new EventProcessingConfig().xStream();
        ProductRestModel back = (ProductRestModel) x.fromXML(x.toXML(dto));
        assertEquals(dto.getProductId(), back.getProductId());
    }
}
