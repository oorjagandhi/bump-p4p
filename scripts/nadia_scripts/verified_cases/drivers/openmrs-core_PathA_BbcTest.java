package bbc;

import com.thoughtworks.xstream.XStream;

import org.openmrs.ImplementationId;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * Reproduces the XStream 1.4.17 -> 1.4.19 behavioural break (security framework
 * enabled-by-default at boundary 1.4.18) through the OpenMRS serialization path.
 *
 * Shape B: adapted production code (whitelisting) was born past the boundary.
 *   preAdaptation() - default pre-hardening behaviour (plain new XStream()).
 *                     PASS on 1.4.17, FAIL (ForbiddenClassException / NoTypePermission)
 *                     on 1.4.19.
 *   adapted()       - configures the whitelist for the driven domain type. PASS on 1.4.19.
 *
 * Both methods use only XStream API present in BOTH 1.4.17 and 1.4.19, and only
 * types that actually resolve in openmrs-api.
 */
public class BbcTest {

	private String buildXml() {
		XStream xstream = new XStream();
		ImplementationId id = new ImplementationId();
		id.setImplementationId("bbc-test");
		// serialization never triggers the deserialization security framework
		return xstream.toXML(id);
	}

	@Test
	public void preAdaptation() {
		XStream xstream = new XStream();
		String xml = buildXml();
		// On 1.4.17 the default framework permits this; on 1.4.19 the security
		// framework is on by default and ImplementationId is not whitelisted,
		// so fromXML throws ForbiddenClassException / NoTypePermission.
		ImplementationId back = (ImplementationId) xstream.fromXML(xml);
		assertEquals("bbc-test", back.getImplementationId());
	}

	@Test
	public void adapted() {
		XStream xstream = new XStream();
		// Whitelist the driven domain type + its package hierarchy, exactly the
		// shape production hardening uses. Self-contained: only real, resolvable
		// types and API present in both 1.4.17 and 1.4.19.
		xstream.allowTypeHierarchy(org.openmrs.OpenmrsObject.class);
		xstream.allowTypes(new Class[] { ImplementationId.class });

		String xml = buildXml();
		ImplementationId back = (ImplementationId) xstream.fromXML(xml);
		assertEquals("bbc-test", back.getImplementationId());
	}
}
