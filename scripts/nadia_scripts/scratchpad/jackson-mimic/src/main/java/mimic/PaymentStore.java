package mimic;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fasterxml.jackson.databind.jsontype.BasicPolymorphicTypeValidator;
import com.fasterxml.jackson.databind.jsontype.PolymorphicTypeValidator;
import com.fasterxml.jackson.databind.jsontype.impl.LaissezFaireSubTypeValidator;

/**
 * Round-trips an {@link Account} (whose {@code holder} is a polymorphic {@link Balance})
 * through Jackson default typing. The three mapper factories mirror the three BBC states.
 *
 * <p>Jackson's default-typing security is OPT-IN: from 2.10 the only API is
 * {@code activateDefaultTyping(PolymorphicTypeValidator)}, and a restrictive validator
 * denies un-allowlisted classes on deserialization (analogous to xstream 1.4.18
 * default-deny). This class varies the security posture the upgrade forces you to choose.
 */
public class PaymentStore {

    /** State 1 — the permissive pre-hardening world (LaissezFaire allows any subtype). */
    public static ObjectMapper permissiveMapper() {
        return JsonMapper.builder()
                .activateDefaultTyping(LaissezFaireSubTypeValidator.instance,
                        ObjectMapper.DefaultTyping.NON_FINAL)
                .build();
    }

    /** State 2 — the default-deny world, UN-ADAPTED: a restrictive validator that does
     *  not allowlist the app's own package, so deserializing {@link Balance} is denied. */
    public static ObjectMapper securedUnadaptedMapper() {
        PolymorphicTypeValidator ptv = BasicPolymorphicTypeValidator.builder()
                .allowIfSubType("java.lang.")   // only JDK base types; NOT mimic.*
                .build();
        return JsonMapper.builder()
                .activateDefaultTyping(ptv, ObjectMapper.DefaultTyping.NON_FINAL)
                .build();
    }

    /** State 3 — the ADAPTATION: restrictive validator that allowlists the app package. */
    public static ObjectMapper adaptedMapper() {
        PolymorphicTypeValidator ptv = BasicPolymorphicTypeValidator.builder()
                .allowIfSubType("mimic.")       // the client's own domain package
                .allowIfSubType("java.")
                .build();
        return JsonMapper.builder()
                .activateDefaultTyping(ptv, ObjectMapper.DefaultTyping.NON_FINAL)
                .build();
    }

    public String toJson(ObjectMapper m, Account a) throws Exception {
        return m.writeValueAsString(a);
    }

    public Account fromJson(ObjectMapper m, String json) throws Exception {
        return m.readValue(json, Account.class);
    }
}
