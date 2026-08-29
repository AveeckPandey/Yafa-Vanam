pipeline {
  agent any

  tools {
    // Configure these exact installation names in Jenkins before the first build.
    nodejs 'Node 24'
    go 'Go 1.23'
  }

  options {
    timestamps()
    disableConcurrentBuilds()
  }

  stages {
    stage('Install dependencies') {
      steps {
        sh 'npm ci'
      }
    }

    stage('Type check') {
      steps {
        sh 'npm run typecheck'
      }
    }

    stage('Frontend tests') {
      steps {
        sh 'npm run test --workspace=@yafa/web'
      }
    }

    stage('Catalogue validation') {
      steps {
        sh 'npm run validate:catalog --workspace=@yafa/web'
      }
    }

    stage('API static checks') {
      steps {
        dir('apps/api') {
          sh 'go vet ./...'
        }
      }
    }

    stage('API unit tests') {
      steps {
        dir('apps/api') {
          sh 'go test ./...'
        }
      }
    }

    // Promotion/coupon redemption guarantees need real PostgreSQL semantics
    // (unique constraints, partial indexes, transactions). They run only
    // against the disposable test database provisioned in Jenkins — never
    // production credentials or data.
    stage('API PostgreSQL integration tests') {
      steps {
        withCredentials([
          string(credentialsId: 'yafa-test-database-url', variable: 'TEST_DATABASE_URL')
        ]) {
          dir('apps/api') {
            sh 'go test ./internal/commerce/... -count=1'
          }
        }
      }
    }

    stage('Production build') {
      steps {
        sh 'npm run build:web'
      }
    }
  }
}
