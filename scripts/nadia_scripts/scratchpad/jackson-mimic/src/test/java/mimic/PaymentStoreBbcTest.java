package mimic;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

/**
 * BBC differential for Jackson default-typing default-deny (PolymorphicTypeValidator),
 * exercising the production PaymentStore round-trip. One test per state:
 *
 *   1_baseline           permissive default typing (pre-hardening)      -> PASS
 *   2_new_lib_old_code   restrictive PTV, app package NOT allowlisted    -> FAIL (denied)
 *   3_adapted            restrictive PTV, app package allowlisted        -> PASS
 *
 * Same round-trip shape as the xstream cases: build a domain object, serialize +
 * deserialize, assert the carried value survives.
 */
public class PaymentStoreBbcTest {

    private final PaymentStore store = new PaymentStore();
    private final Account account = new Account("alice", new Balance("USD", 4200));

    @Test
    void state1_baseline_permissive() throws Exception {
        ObjectMapper m = PaymentStore.permissiveMapper();
        String json = store.toJson(m, account);
        Account back = store.fromJson(m, json);
        assertEquals(4200, ((Balance) back.holder).amount);
    }

    @Test
    void state2_secured_unadapted_breaks() throws Exception {
        ObjectMapper m = PaymentStore.securedUnadaptedMapper();
        String json = store.toJson(m, account);
        // default-deny: the app's own Balance is not allowlisted -> deserialization is denied
        Exception e = assertThrows(Exception.class, () -> store.fromJson(m, json));
        String msg = String.valueOf(e.getMessage()) + String.valueOf(e.getCause());
        if (!(msg.contains("PolymorphicTypeValidator") || msg.contains("denied")
                || msg.contains("not resolve") || msg.contains("Could not resolve type id"))) {
            throw new AssertionError("expected a PTV-denied failure, got: " + e, e);
        }
    }

    @Test
    void state3_adapted_passes() throws Exception {
        ObjectMapper m = PaymentStore.adaptedMapper();
        String json = store.toJson(m, account);
        Account back = store.fromJson(m, json);
        assertEquals(4200, ((Balance) back.holder).amount);
    }
}
