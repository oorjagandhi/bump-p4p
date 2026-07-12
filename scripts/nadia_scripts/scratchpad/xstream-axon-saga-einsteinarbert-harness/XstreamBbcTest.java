package bbc;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.progressivecoder.ecommerce.commands.CreateOrderCommand;
import com.progressivecoder.ordermanagement.orderservice.config.XStreamAutoConfiguration;
import com.thoughtworks.xstream.XStream;
import java.math.BigDecimal;
import java.util.Collections;
import java.util.Optional;
import org.junit.jupiter.api.Test;

/**
 * BBC differential for xstream 1.4.18 default-deny, exercising the REAL production
 * adaptation XStreamAutoConfiguration (allowTypesByWildcard "com.progressivecoder.ecommerce.**").
 *
 * plainXStream()      = Axon's pre-adaptation default (plain new XStream(), no allowlist)
 * configuredXStream() = the production adaptation: the real XStreamAutoConfiguration.xStream()
 *                       bean + XStreamConverterAutoConfiguration.registerConverters() allowlist.
 *
 * At xstream 1.4.17 both PASS. At 1.4.18+ plainXStream FAILS (ForbiddenClassException
 * on CreateOrderCommand) while configuredXStream PASSES -> the adaptation resolves the break.
 */
public class XstreamBbcTest {

    private final CreateOrderCommand cmd =
            new CreateOrderCommand("order-1", "book", new BigDecimal("9.99"), "USD", "CREATED");

    @Test
    public void plainXStream() {
        XStream x = new XStream();
        CreateOrderCommand back = (CreateOrderCommand) x.fromXML(x.toXML(cmd));
        assertEquals(cmd.orderId, back.orderId);
    }

    @Test
    public void configuredXStream() {
        XStreamAutoConfiguration cfg = new XStreamAutoConfiguration();
        XStream x = cfg.xStream(Optional.empty());
        new XStreamAutoConfiguration.XStreamConverterAutoConfiguration(x, Collections.emptyList())
                .registerConverters();
        CreateOrderCommand back = (CreateOrderCommand) x.fromXML(x.toXML(cmd));
        assertEquals(cmd.orderId, back.orderId);
    }
}
