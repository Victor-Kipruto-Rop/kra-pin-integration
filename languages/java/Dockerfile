FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /app
COPY pom.xml .
COPY src ./src
RUN mvn -q -DskipTests package
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /app/target/kra-pin-service-1.0.0.jar app.jar
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["java","-jar","app.jar"]
