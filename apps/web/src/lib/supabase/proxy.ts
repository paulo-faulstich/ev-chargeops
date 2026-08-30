import { createServerClient } from "@supabase/ssr";
import { type NextRequest, NextResponse } from "next/server";

import { isFixtureAuth } from "@/lib/auth/mode";

function redirectWithCookies(
  request: NextRequest,
  pathname: string,
  response: NextResponse,
): NextResponse {
  const destination = request.nextUrl.clone();
  destination.pathname = pathname;
  destination.search = "";

  const redirectResponse = NextResponse.redirect(destination);
  response.cookies.getAll().forEach((cookie) =>
    redirectResponse.cookies.set(cookie),
  );
  return redirectResponse;
}

export async function updateSession(request: NextRequest) {
  const isLoginRoute =
    request.nextUrl.pathname === "/login" ||
    request.nextUrl.pathname.startsWith("/login/");

  if (isFixtureAuth()) {
    const isAuthenticated =
      request.headers.get("x-ev-auth-test") !== "missing";

    if (!isAuthenticated && !isLoginRoute) {
      return redirectWithCookies(
        request,
        "/login",
        NextResponse.next({ request }),
      );
    }
    if (isAuthenticated && isLoginRoute) {
      return redirectWithCookies(
        request,
        "/dashboard",
        NextResponse.next({ request }),
      );
    }
    return NextResponse.next({ request });
  }

  let response = NextResponse.next({ request });
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll(items) {
          items.forEach(({ name, value }) =>
            request.cookies.set(name, value),
          );
          response = NextResponse.next({ request });
          items.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options),
          );
        },
      },
    },
  );

  const { data, error } = await supabase.auth.getClaims();
  const isAuthenticated = !error && Boolean(data?.claims?.sub);

  if (!isAuthenticated && !isLoginRoute) {
    return redirectWithCookies(request, "/login", response);
  }
  if (isAuthenticated && isLoginRoute) {
    return redirectWithCookies(request, "/dashboard", response);
  }

  return response;
}
