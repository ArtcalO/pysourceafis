// SPDX-License-Identifier: Apache-2.0
package io.github.pysourceafis;

import com.fasterxml.jackson.annotation.JsonAutoDetect.Visibility;
import com.fasterxml.jackson.annotation.PropertyAccessor;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.cbor.CBORFactory;
import com.machinezoo.sourceafis.FingerprintCompatibility;
import com.machinezoo.sourceafis.FingerprintImage;
import com.machinezoo.sourceafis.FingerprintImageOptions;
import com.machinezoo.sourceafis.FingerprintTemplate;
import java.io.IOException;

/**
 * Static helpers called from Python. Only documented SourceAFIS public API is
 * used for extraction and matching; the CBOR reader only inspects the
 * documented template fields to report the minutia count.
 */
public final class Bridge {
    private Bridge() {}

    /** Version of the bundled SourceAFIS engine, e.g. "3.18.1". */
    public static String sourceafisVersion() {
        return FingerprintCompatibility.version();
    }

    /** Extracts a template from 8-bit grayscale pixels (row-major, 0 = black). */
    public static FingerprintTemplate extract(int width, int height, byte[] pixels, double dpi) {
        return new FingerprintTemplate(new FingerprintImage(width, height, pixels, new FingerprintImageOptions().dpi(dpi)));
    }

    /** Extracts a template from an encoded image (PNG, JPEG, BMP, WSQ, ...) decoded by SourceAFIS itself. */
    public static FingerprintTemplate extractEncoded(byte[] image, double dpi) {
        return new FingerprintTemplate(new FingerprintImage(image, new FingerprintImageOptions().dpi(dpi)));
    }

    static final class Persisted {
        public String version;
        public String types;
    }

    private static final ObjectMapper MAPPER = new ObjectMapper(new CBORFactory())
        .setVisibility(PropertyAccessor.FIELD, Visibility.ANY)
        .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);

    /** Number of minutiae in a serialized native template (-1 if it cannot be read). */
    public static int minutiaeCount(byte[] serialized) {
        try {
            Persisted p = MAPPER.readValue(serialized, Persisted.class);
            return p.types == null ? 0 : p.types.length();
        } catch (IOException ex) {
            return -1;
        }
    }

    /** SourceAFIS version recorded inside a serialized native template ("" if unknown). */
    public static String templateVersion(byte[] serialized) {
        try {
            Persisted p = MAPPER.readValue(serialized, Persisted.class);
            return p.version == null ? "" : p.version;
        } catch (IOException ex) {
            return "";
        }
    }
}
