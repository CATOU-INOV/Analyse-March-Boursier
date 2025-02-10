import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;

public class TestMariaDBConnection {
    public static void main(String[] args) {
        String jdbcURL = "jdbc:mariadb://localhost:3306/Meteo";
        String username = "nifi_user";
        String password = "nifi_password";

        try {
            // Load the MariaDB driver explicitly
            Class.forName("org.mariadb.jdbc.Driver");

            // Establish connection
            Connection connection = DriverManager.getConnection(jdbcURL, username, password);
            System.out.println("Connection successful!");

            // Close connection
            connection.close();
        } catch (ClassNotFoundException e) {
            System.out.println("MariaDB Driver not found.");
            e.printStackTrace();
        } catch (SQLException e) {
            System.out.println("SQL Exception occurred.");
            e.printStackTrace();
        }
    }
}

