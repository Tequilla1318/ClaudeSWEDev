plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// Release signing comes from the environment (CI secret or a local keystore that is never committed).
// Without it, the release build falls back to the debug key so `assembleRelease` still works.
val keystorePath: String? = System.getenv("AUDIO_DIARY_KEYSTORE")
val keystorePassword: String? = System.getenv("AUDIO_DIARY_KEYSTORE_PASSWORD")
val hasReleaseKey = !keystorePath.isNullOrBlank() && file(keystorePath!!).exists() && !keystorePassword.isNullOrBlank()

android {
    namespace = "dev.claudeswe.audiodiary"
    compileSdk = 35

    defaultConfig {
        applicationId = "dev.claudeswe.audiodiary"
        minSdk = 29
        targetSdk = 35
        versionCode = (System.getenv("AUDIO_DIARY_VERSION_CODE") ?: "1").toInt()
        versionName = "0.1.${System.getenv("AUDIO_DIARY_VERSION_CODE") ?: "1"}"
    }

    signingConfigs {
        if (hasReleaseKey) {
            create("release") {
                storeFile = file(keystorePath!!)
                storePassword = keystorePassword
                keyAlias = "audiodiary"
                keyPassword = keystorePassword
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = if (hasReleaseKey) signingConfigs.getByName("release") else signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
    }
    testOptions {
        unitTests.isReturnDefaultValues = true
    }
    lint {
        abortOnError = true
        checkReleaseBuilds = false
        // Pinned dependency versions are deliberate; don't fail the build because newer ones exist.
        disable += setOf("GradleDependency", "NewerVersionAvailable", "AndroidGradlePluginVersion", "OldTargetApi")
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2025.06.00")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-core")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.9.1")
    implementation("androidx.core:core-ktx:1.16.0")
    implementation("androidx.work:work-runtime-ktx:2.10.1")
    implementation("androidx.media3:media3-exoplayer:1.7.1")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    constraints {
        // Media3 pulls Guava 33.3.1, which has GHSA-xxph-c9ww-hj94 (deserialization DoS). The app never
        // deserializes Java objects so it isn't reachable, but pin the fixed version anyway.
        implementation("com.google.guava:guava:33.7.2-android")
    }

    testImplementation("junit:junit:4.13.2")
    testImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")
    testImplementation("com.squareup.okhttp3:okhttp-tls:4.12.0")
    testImplementation("org.json:json:20240303")
}
