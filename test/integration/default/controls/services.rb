# frozen_string_literal: true

control 'incus.service.running' do
  title 'The service should be installed, enabled and running'

  describe service('incus') do
    it { should be_installed }
    it { should be_enabled }
    it { should be_running }
  end
end
