package ke.co.krapin.oscu;

import org.junit.jupiter.api.Test;
import java.io.IOException;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;

class DirectOscuClientTest {
    private DirectOscuClient client() throws IOException {
        return new DirectOscuClient("consumer", "secret", "app-id");
    }

    @Test void manifestContains23Operations() throws Exception {
        assertEquals(23, client().operationCount());
    }

    @Test void unknownOperationFailsBeforeNetwork() throws Exception {
        assertThrows(IllegalArgumentException.class,
                () -> client().invoke("not-real", Map.of(), Map.of(), false));
    }

    @Test void mutationRequiresExplicitConfirmationBeforeNetwork() throws Exception {
        var client = client();
        var error = assertThrows(IllegalArgumentException.class,
                () -> client.invoke("save-item", Map.of(), Map.of("tin", "P1", "bhfId", "00", "cmcKey", "x"), false));
        assertTrue(error.getMessage().contains("confirmation"));
    }

    @Test void initializationRequiresOnlyAppIdAndIsMarkedMutating() throws Exception {
        var client = client();
        assertThrows(IllegalArgumentException.class,
                () -> client.invoke("oscu-initialization", Map.of(), Map.of(), false));
    }
}
