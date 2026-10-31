package ke.co.krapin;
import org.junit.jupiter.api.Test;import static org.junit.jupiter.api.Assertions.*;
class ApplicationTest {@Test void applicationHasSandboxOrProductionBase(){var app=new Application();assertTrue(app.base.equals("https://sbx.kra.go.ke")||app.base.equals("https://api.kra.go.ke"));} @Test void catalogContainsAll22Services(){assertEquals(22,Application.SERVICES.size());}}
