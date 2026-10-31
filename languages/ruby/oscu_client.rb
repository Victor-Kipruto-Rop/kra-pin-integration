require 'json'
require 'net/http'
require 'uri'
require 'base64'
require 'timeout'

module KraPin
  class OscuError < StandardError
    attr_reader :code, :outcome_unknown
    def initialize(code, message, outcome_unknown: false)
      super(message)
      @code = code
      @outcome_unknown = outcome_unknown
    end
  end

  # Server-side client for KRA direct eTIMS OSCU sandbox operations.
  class DirectOscuClient
    TOKEN_URL = 'https://sbx.kra.go.ke/v1/token/generate?grant_type=client_credentials'
    API_BASE = 'https://sbx.kra.go.ke/etims-oscu/api/v1'

    attr_reader :operations

    def initialize(consumer_key:, consumer_secret:, app_id:, timeout: 20, transport: nil)
      raise ArgumentError, 'OSCU consumer credentials and app ID are required' if [consumer_key, consumer_secret, app_id].any?(&:empty?)
      raise ArgumentError, 'timeout must be positive' unless timeout.positive?
      @consumer_key, @consumer_secret, @app_id = consumer_key, consumer_secret, app_id
      @timeout, @transport = timeout, transport
      manifest = JSON.parse(File.read(File.join(__dir__, 'etims_oscu_endpoints.json')))
      @operations = manifest.fetch('operations').to_h { |operation| [operation.fetch('id'), operation] }
      @access_token = nil
      @token_expires_at = 0
    end

    def invoke(operation_id, payload, tenant_context = {}, confirm_mutation: false)
      operation = @operations[operation_id]
      raise ArgumentError, 'Unknown OSCU operation ID' unless operation
      raise ArgumentError, 'payload must be a JSON object' unless payload.is_a?(Hash)
      if operation.fetch('mutates') && !confirm_mutation
        raise ArgumentError, 'Operation may mutate KRA state; explicit confirmation required'
      end

      headers = {
        'apigee_app_id' => @app_id,
        'Accept' => 'application/json',
        'Content-Type' => 'application/json'
      }
      operation.fetch('headers').each do |name|
        next if name == 'apigee_app_id'
        value = tenant_context[name]
        raise ArgumentError, "Missing required OSCU context: #{name}" if value.nil? || value.empty?
        headers[name] = value
      end
      headers['Authorization'] = "Bearer #{access_token}"
      begin
        response = request("#{API_BASE}#{operation.fetch('path')}", headers, JSON.generate(payload))
      rescue StandardError => error
        if operation.fetch('mutates')
          raise OscuError.new('oscu_outcome_unknown', 'KRA OSCU request outcome is unknown; reconcile before resubmitting', outcome_unknown: true), cause: error
        end
        raise OscuError.new('oscu_upstream_unreachable', 'Could not reach KRA OSCU'), cause: error
      end
      unless response[:status].between?(200, 299)
        raise OscuError.new('oscu_request_rejected', "KRA OSCU rejected request (HTTP #{response[:status]})")
      end
      return nil if response[:body].to_s.strip.empty?
      JSON.parse(response[:body])
    rescue JSON::ParserError
      raise OscuError.new('oscu_invalid_response', 'KRA OSCU returned a non-JSON response')
    end

    private

    def access_token
      return @access_token if @access_token && Time.now.to_i < @token_expires_at - 60
      basic = Base64.strict_encode64("#{@consumer_key}:#{@consumer_secret}")
      response = request(TOKEN_URL, { 'Authorization' => "Basic #{basic}", 'Accept' => 'application/json' }, nil)
      unless response[:status].between?(200, 299)
        raise OscuError.new('oscu_auth_failed', 'KRA rejected OSCU token request')
      end
      body = JSON.parse(response[:body])
      token = body['access_token']
      raise OscuError.new('oscu_auth_failed', 'KRA returned an invalid OSCU token response') unless token.is_a?(String) && !token.empty?
      ttl = body.fetch('expires_in', 3600).to_i
      @access_token = token
      @token_expires_at = Time.now.to_i + (ttl.positive? ? ttl : 3600)
      @access_token
    rescue JSON::ParserError
      raise OscuError.new('oscu_auth_failed', 'KRA returned an invalid OSCU token response')
    end

    def request(url, headers, body)
      return @transport.call(url, headers, body, @timeout) if @transport
      uri = URI(url)
      http = Net::HTTP.new(uri.host, uri.port)
      http.use_ssl = true
      http.open_timeout = [@timeout, 10].min
      http.read_timeout = @timeout
      req = body.nil? ? Net::HTTP::Get.new(uri) : Net::HTTP::Post.new(uri)
      headers.each { |key, value| req[key] = value }
      req.body = body if body
      response = http.start { |connection| connection.request(req) }
      { status: response.code.to_i, body: response.body.to_s }
    end
  end
end
