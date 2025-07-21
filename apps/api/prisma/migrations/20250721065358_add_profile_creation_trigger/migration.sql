  -- migration.sql
  -- CreateTable statements for your schema...

  -- Add the profile creation trigger
  CREATE OR REPLACE FUNCTION create_profile_on_signup()
  RETURNS TRIGGER
  SECURITY DEFINER
  LANGUAGE plpgsql
  AS $$
  DECLARE
    new_profile_id UUID;
    display_name TEXT;
  BEGIN
    -- Extract display_name from user metadata, fallback to null if not provided
    display_name := COALESCE(NEW.raw_user_meta_data->>'display_name', NULL);

    -- Create profile record
    INSERT INTO public.profiles (id, email, display_name, created_at, updated_at)
    VALUES (
      gen_random_uuid(),
      NEW.email,
      display_name,
      NOW(),
      NOW()
    )
    RETURNING id INTO new_profile_id;

    -- Create auth_link record to connect Supabase auth user to profile
    INSERT INTO public.auth_links (id, auth_id, profile_id, provider, created_at)
    VALUES (
      gen_random_uuid(),
      NEW.id,
      new_profile_id,
      'email',
      NOW()
    );

    RETURN NEW;
  END;
  $$;

  -- Create trigger on auth.users table
  DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
  CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION create_profile_on_signup();